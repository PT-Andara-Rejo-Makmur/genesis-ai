from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from genesis.skills.loader import SkillDescriptor, SkillReference

_TOKEN = re.compile(r"[a-z0-9]+")


class SkillSelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    MISSING_PACKAGE = "MISSING_PACKAGE"
    NOT_RELEVANT = "NOT_RELEVANT"
    REQUIRED_TOOL_UNAVAILABLE = "REQUIRED_TOOL_UNAVAILABLE"
    REQUIRED_PERMISSION_UNAVAILABLE = "REQUIRED_PERMISSION_UNAVAILABLE"
    REQUIRED_SCOPE_UNAVAILABLE = "REQUIRED_SCOPE_UNAVAILABLE"


class SkillCandidateOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reference: SkillReference
    status: SkillSelectionStatus
    relevance_score: int = Field(ge=0)
    reason: str = Field(min_length=1)
    missing_tool_ids: tuple[str, ...] = ()
    descriptor: SkillDescriptor | None = None


class SkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    selected: tuple[SkillCandidateOutcome, ...]
    unavailable: tuple[SkillCandidateOutcome, ...]
    effective_tool_ids: tuple[str, ...]


class SkillSelector:
    """Filter Backend authorization first, then rank explainably and deterministically."""

    def select(
        self,
        descriptors: Sequence[SkillDescriptor],
        *,
        authorized_refs: Sequence[SkillReference],
        goal: str,
        backend_allowed_tool_ids: Sequence[str],
        backend_permission_refs: Sequence[str] = (),
        backend_scope_refs: Sequence[str] = (),
        agent_allowed_tool_ids: Sequence[str] | None = None,
        capability_context: Sequence[str] = (),
        maximum_selected: int = 1,
    ) -> SkillSelection:
        if maximum_selected < 1:
            raise ValueError("maximum_selected must be at least one")
        authorized = {(item.skill_id, item.skill_version): item for item in authorized_refs}
        by_id: dict[str, list[SkillDescriptor]] = {}
        for descriptor in descriptors:
            by_id.setdefault(descriptor.specification.skill_id, []).append(descriptor)

        backend_tools = frozenset(backend_allowed_tool_ids)
        effective_tools = backend_tools
        if agent_allowed_tool_ids is not None:
            effective_tools &= frozenset(agent_allowed_tool_ids)

        unavailable: list[SkillCandidateOutcome] = []
        eligible: list[SkillCandidateOutcome] = []
        for descriptor in descriptors:
            reference = descriptor.reference
            key = (reference.skill_id, reference.skill_version)
            if key not in authorized:
                unavailable.append(
                    SkillCandidateOutcome(
                        reference=reference,
                        status=SkillSelectionStatus.UNAUTHORIZED,
                        relevance_score=0,
                        reason="Filesystem discovery does not authorize this skill reference.",
                    )
                )
                continue
            score, reason = self._relevance(descriptor, goal, capability_context)
            if score == 0:
                unavailable.append(
                    SkillCandidateOutcome(
                        reference=reference,
                        status=SkillSelectionStatus.NOT_RELEVANT,
                        relevance_score=0,
                        reason="Authorized skill metadata does not match the requested goal.",
                        descriptor=descriptor,
                    )
                )
                continue
            missing = tuple(
                sorted(set(descriptor.specification.required_tool_ids) - effective_tools)
            )
            if missing:
                unavailable.append(
                    SkillCandidateOutcome(
                        reference=reference,
                        status=SkillSelectionStatus.REQUIRED_TOOL_UNAVAILABLE,
                        relevance_score=score,
                        reason=(
                            "A required tool is absent from the effective Backend/Agent allowlist."
                        ),
                        missing_tool_ids=missing,
                        descriptor=descriptor,
                    )
                )
                continue
            missing_permissions = tuple(
                sorted(set(descriptor.specification.permission_refs) - set(backend_permission_refs))
            )
            if missing_permissions:
                unavailable.append(
                    SkillCandidateOutcome(
                        reference=reference,
                        status=SkillSelectionStatus.REQUIRED_PERMISSION_UNAVAILABLE,
                        relevance_score=score,
                        reason="A permission prerequisite is absent from Backend authority.",
                        descriptor=descriptor,
                    )
                )
                continue
            missing_scopes = tuple(
                sorted(set(descriptor.specification.scope_refs) - set(backend_scope_refs))
            )
            if missing_scopes:
                unavailable.append(
                    SkillCandidateOutcome(
                        reference=reference,
                        status=SkillSelectionStatus.REQUIRED_SCOPE_UNAVAILABLE,
                        relevance_score=score,
                        reason="A scope prerequisite is absent from Backend authority.",
                        descriptor=descriptor,
                    )
                )
                continue
            eligible.append(
                SkillCandidateOutcome(
                    reference=reference,
                    status=SkillSelectionStatus.SELECTED,
                    relevance_score=score,
                    reason=reason,
                    descriptor=descriptor,
                )
            )

        discovered_refs = {
            (item.specification.skill_id, item.specification.skill_version) for item in descriptors
        }
        for reference in authorized_refs:
            key = (reference.skill_id, reference.skill_version)
            if key in discovered_refs:
                continue
            status = (
                SkillSelectionStatus.VERSION_MISMATCH
                if reference.skill_id in by_id
                else SkillSelectionStatus.MISSING_PACKAGE
            )
            reason = (
                "Authorized skill version does not match any discovered package."
                if status is SkillSelectionStatus.VERSION_MISMATCH
                else "Authorized skill package is not available on this runtime."
            )
            unavailable.append(
                SkillCandidateOutcome(
                    reference=reference,
                    status=status,
                    relevance_score=0,
                    reason=reason,
                )
            )

        eligible.sort(
            key=lambda item: (
                -item.relevance_score,
                item.reference.skill_id,
                item.reference.skill_version,
            )
        )
        selected = tuple(eligible[:maximum_selected])
        for item in eligible[maximum_selected:]:
            unavailable.append(
                item.model_copy(
                    update={
                        "status": SkillSelectionStatus.NOT_RELEVANT,
                        "reason": "A higher-ranked authorized skill filled the bounded selection.",
                    }
                )
            )
        unavailable.sort(
            key=lambda item: (
                item.reference.skill_id,
                item.reference.skill_version,
                item.status.value,
            )
        )
        return SkillSelection(
            selected=selected,
            unavailable=tuple(unavailable),
            effective_tool_ids=tuple(sorted(effective_tools)),
        )

    @staticmethod
    def _relevance(
        descriptor: SkillDescriptor,
        goal: str,
        capability_context: Sequence[str],
    ) -> tuple[int, str]:
        query_tokens = set(_TOKEN.findall(" ".join((goal, *capability_context)).lower()))
        specification = descriptor.specification
        metadata = " ".join(
            (
                specification.name,
                specification.description,
                specification.purpose,
                *specification.when_to_use,
            )
        )
        matches = sorted(query_tokens & set(_TOKEN.findall(metadata.lower())))
        if not matches:
            return 0, "No deterministic metadata term matched the goal."
        return len(matches), "Matched authorized metadata terms: " + ", ".join(matches[:8]) + "."
