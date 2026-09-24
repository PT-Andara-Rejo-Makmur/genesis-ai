"""Generic bounded responsibility decomposition."""

from __future__ import annotations

import re

from genesis.control_plane.workforce.models import (
    InterpretedResponsibility,
    RequirementUnderstanding,
    ResponsibilityCandidate,
)


class DecompositionPlanner:
    """Decide lineage and atomicity independently from interpretation and graph building."""

    def __init__(self, *, max_depth: int = 2) -> None:
        if not 0 <= max_depth <= 8:
            raise ValueError("max_depth must be between 0 and 8")
        self.max_depth = max_depth

    async def decompose(
        self,
        understanding: RequirementUnderstanding,
    ) -> tuple[InterpretedResponsibility, ...]:
        candidates = {item.identity: item for item in understanding.candidates}
        declared_parents = self._declared_parents(understanding.candidates)
        parent_by_identity: dict[str, str | None] = {}
        for candidate in understanding.candidates:
            if candidate.identity == understanding.root_identity:
                parent_by_identity[candidate.identity] = candidate.parent_hint
            elif candidate.parent_hint is not None:
                parent_by_identity[candidate.identity] = candidate.parent_hint
            elif candidate.identity in declared_parents:
                parent_by_identity[candidate.identity] = declared_parents[candidate.identity]
            else:
                parent_by_identity[candidate.identity] = understanding.root_identity

        children: dict[str, set[str]] = {identity: set() for identity in candidates}
        for identity, parent_identity in parent_by_identity.items():
            if parent_identity in children:
                children[parent_identity].add(identity)

        responsibilities = tuple(
            InterpretedResponsibility(
                identity=candidate.identity,
                purpose=candidate.purpose,
                parent_identity=parent_by_identity[candidate.identity],
                atomic=not children[candidate.identity],
                input_semantics=(
                    candidate.input_semantics
                    or (f"{candidate.identity} bounded input",)
                ),
                output_semantics=(
                    candidate.output_semantics
                    or (f"{candidate.identity} reviewable result",)
                ),
                domain_tags=self._domain_tags(
                    candidate.identity,
                    candidates,
                    children,
                    active=frozenset(),
                ),
                required_capability_ids=candidate.required_capability_ids,
                required_skill_ids=candidate.required_skill_ids,
                required_tool_ids=candidate.required_tool_ids,
                permission_refs=candidate.permission_refs,
                scope_refs=candidate.scope_refs,
            )
            for candidate in understanding.candidates
        )
        return tuple(sorted(responsibilities, key=lambda item: item.identity))

    @staticmethod
    def _declared_parents(
        candidates: tuple[ResponsibilityCandidate, ...],
    ) -> dict[str, str]:
        declarations: dict[str, list[str]] = {}
        for candidate in candidates:
            for child_identity in candidate.child_identities:
                declarations.setdefault(child_identity, []).append(candidate.identity)
        return {
            child_identity: sorted(parent_identities)[0]
            for child_identity, parent_identities in declarations.items()
        }

    @classmethod
    def _domain_tags(
        cls,
        identity: str,
        candidates: dict[str, ResponsibilityCandidate],
        children: dict[str, set[str]],
        *,
        active: frozenset[str],
    ) -> tuple[str, ...]:
        candidate = candidates[identity]
        if candidate.domain_tags:
            return candidate.domain_tags
        own_tags = set(re.findall(r"[a-z0-9]+", identity.casefold()))
        if identity in active:
            return tuple(sorted(own_tags))
        descendant_tags = {
            tag
            for child_identity in children[identity]
            for tag in cls._domain_tags(
                child_identity,
                candidates,
                children,
                active=active | {identity},
            )
        }
        return tuple(sorted(own_tags | descendant_tags))
