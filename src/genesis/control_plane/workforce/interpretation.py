"""Deterministic requirement interpretation behind a future ModelGateway port."""

from __future__ import annotations

import re
from dataclasses import dataclass

from genesis.control_plane.workforce.models import (
    InterpretedResponsibility,
    RequirementUnderstanding,
    ResponsibilityRequirement,
    WorkforceRequirement,
)


@dataclass(frozen=True, slots=True)
class ResponsibilityRule:
    identity: str
    phrases: tuple[str, ...]
    purpose: str
    parent_identity: str | None = None
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()


DEFAULT_RESPONSIBILITY_RULES = (
    ResponsibilityRule(
        identity="schedule.monitoring",
        phrases=("schedule monitoring", "monitor schedule", "pemantauan jadwal"),
        purpose="Monitor schedule performance and surface measurable variance.",
        input_semantics=("schedule baseline", "schedule observation"),
        output_semantics=("schedule variance finding",),
        domain_tags=("monitoring", "performance", "schedule"),
    ),
    ResponsibilityRule(
        identity="quality.monitoring",
        phrases=("quality monitoring", "monitor quality", "pemantauan kualitas"),
        purpose="Monitor quality signals and coordinate narrower quality checks.",
        input_semantics=("quality observation",),
        output_semantics=("quality finding",),
        domain_tags=("quality", "monitoring", "compliance", "defect"),
    ),
    ResponsibilityRule(
        identity="material.compliance",
        phrases=("material compliance", "kepatuhan material"),
        purpose="Evaluate material observations against supplied compliance criteria.",
        parent_identity="quality.monitoring",
        input_semantics=("material observation", "compliance criteria"),
        output_semantics=("material compliance finding",),
        domain_tags=("quality", "compliance"),
    ),
    ResponsibilityRule(
        identity="defect.detection",
        phrases=("defect detection", "detect defects", "deteksi cacat"),
        purpose="Detect and report observable defects without authorizing remediation.",
        parent_identity="quality.monitoring",
        input_semantics=("quality observation",),
        output_semantics=("defect finding",),
        domain_tags=("quality", "defect"),
    ),
    ResponsibilityRule(
        identity="vendor.risk.analysis",
        phrases=("vendor risk analysis", "vendor risk", "analisis risiko vendor"),
        purpose="Analyze vendor risk signals and produce reviewable recommendations.",
        input_semantics=("vendor evidence", "risk criteria"),
        output_semantics=("vendor risk finding",),
        domain_tags=("vendor", "risk", "analysis"),
    ),
)


class DeterministicRequirementInterpreter:
    """A replaceable interpreter with no provider dependency or side effects."""

    def __init__(
        self,
        rules: tuple[ResponsibilityRule, ...] = DEFAULT_RESPONSIBILITY_RULES,
    ) -> None:
        self._rules = tuple(sorted(rules, key=lambda item: item.identity))

    async def interpret(self, requirement: WorkforceRequirement) -> RequirementUnderstanding:
        normalized = " ".join(requirement.requirement.statement.casefold().split())
        if requirement.responsibility_hints:
            responsibilities = self._from_hints(requirement)
            root_identity = self._root_identity(responsibilities)
            rationale: tuple[str, ...] = (
                "Used caller-supplied structured responsibility semantics.",
            )
        else:
            responsibilities = self._from_rules(requirement, normalized)
            root_identity = self._root_identity(responsibilities)
            rationale = (
                "Applied deterministic responsibility rules; a ModelGateway interpreter can "
                "replace this port.",
                "Decomposition stops at responsibilities with explicit input, output, failure, "
                "and evaluation semantics.",
            )
        return RequirementUnderstanding(
            normalized_requirement=normalized,
            root_identity=root_identity,
            responsibilities=responsibilities,
            rationale=rationale,
        )

    def _from_hints(
        self, requirement: WorkforceRequirement
    ) -> tuple[InterpretedResponsibility, ...]:
        context = requirement.requirement.execution_context
        return tuple(
            self._from_hint(hint, context.permission_refs, context.scope_refs)
            for hint in sorted(requirement.responsibility_hints, key=lambda item: item.identity)
        )

    @staticmethod
    def _from_hint(
        hint: ResponsibilityRequirement,
        inherited_permissions: tuple[str, ...],
        inherited_scopes: tuple[str, ...],
    ) -> InterpretedResponsibility:
        return InterpretedResponsibility(
            identity=hint.identity,
            purpose=hint.purpose,
            parent_identity=hint.parent_identity,
            atomic=hint.atomic,
            input_semantics=tuple(sorted(set(hint.input_semantics))),
            output_semantics=tuple(sorted(set(hint.output_semantics))),
            domain_tags=tuple(sorted(set(hint.domain_tags))),
            required_capability_ids=tuple(sorted(set(hint.required_capability_ids))),
            required_skill_ids=tuple(sorted(set(hint.required_skill_ids))),
            required_tool_ids=tuple(sorted(set(hint.required_tool_ids))),
            permission_refs=tuple(
                sorted(
                    set(
                        inherited_permissions
                        if hint.permission_refs is None
                        else hint.permission_refs
                    )
                )
            ),
            scope_refs=tuple(
                sorted(set(inherited_scopes if hint.scope_refs is None else hint.scope_refs))
            ),
        )

    def _from_rules(
        self, requirement: WorkforceRequirement, normalized: str
    ) -> tuple[InterpretedResponsibility, ...]:
        matched = [rule for rule in self._rules if any(p in normalized for p in rule.phrases)]
        matched_ids = {rule.identity for rule in matched}
        for rule in self._rules:
            if rule.identity in matched_ids:
                continue
            if any(item.parent_identity == rule.identity for item in matched):
                matched.append(rule)
                matched_ids.add(rule.identity)

        root_identity = self._derive_root_identity(normalized)
        child_tags = {tag for rule in matched for tag in rule.domain_tags}
        context = requirement.requirement.execution_context
        root = InterpretedResponsibility(
            identity=root_identity,
            purpose=requirement.requirement.statement.strip(),
            atomic=not matched,
            input_semantics=("business requirement",),
            output_semantics=("reviewable workforce result",),
            domain_tags=tuple(sorted(child_tags or {root_identity.split(".")[0]})),
            required_capability_ids=tuple(sorted(set(requirement.required_capability_ids))),
            required_skill_ids=tuple(sorted(set(requirement.required_skill_ids))),
            required_tool_ids=tuple(sorted(set(requirement.required_tool_ids))),
            permission_refs=tuple(sorted(set(context.permission_refs))),
            scope_refs=tuple(sorted(set(context.scope_refs))),
        )
        children = tuple(
            InterpretedResponsibility(
                identity=rule.identity,
                purpose=rule.purpose,
                parent_identity=(
                    rule.parent_identity if rule.parent_identity in matched_ids else root_identity
                ),
                atomic=not any(item.parent_identity == rule.identity for item in matched),
                input_semantics=rule.input_semantics,
                output_semantics=rule.output_semantics,
                domain_tags=tuple(sorted(set(rule.domain_tags))),
                permission_refs=tuple(sorted(set(context.permission_refs))),
                scope_refs=tuple(sorted(set(context.scope_refs))),
            )
            for rule in sorted(matched, key=lambda item: item.identity)
        )
        return (root, *children)

    @staticmethod
    def _root_identity(responsibilities: tuple[InterpretedResponsibility, ...]) -> str:
        roots = tuple(item.identity for item in responsibilities if item.parent_identity is None)
        candidates = roots or tuple(item.identity for item in responsibilities)
        return sorted(candidates)[0]

    @staticmethod
    def _derive_root_identity(normalized: str) -> str:
        if "vendor" in normalized and ("performance" in normalized or "kinerja" in normalized):
            return "vendor.performance"
        tokens = re.findall(r"[a-z0-9]+", normalized)
        meaningful = [
            token
            for token in tokens
            if token not in {"agent", "buat", "create", "untuk", "and", "dan", "yang"}
        ]
        identity = ".".join(meaningful[:4]) or "general.requirement"
        return identity[:128]
