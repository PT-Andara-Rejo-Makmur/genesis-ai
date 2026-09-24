"""Structured, deterministic and reuse-first capability matching."""

import re
from collections.abc import Sequence

from genesis.control_plane.workforce.models import (
    CapabilityMatch,
    CapabilityNode,
    CapabilityProfile,
    WorkforceRegistrySnapshot,
)


class DeterministicCapabilityMatcher:
    def match(
        self,
        node: CapabilityNode,
        registry: WorkforceRegistrySnapshot,
        *,
        excluded_capability_ids: Sequence[str] = (),
    ) -> CapabilityMatch:
        excluded = set(excluded_capability_ids)
        ranked = sorted(
            (
                (self._score(node, profile), profile)
                for profile in registry.capability_profiles
                if profile.catalog_item.capability_id not in excluded
            ),
            key=lambda pair: (-pair[0], pair[1].catalog_item.capability_id),
        )
        if not ranked or ranked[0][0] < 100:
            return CapabilityMatch(
                node_id=node.node_id,
                decision="CREATE",
                score=ranked[0][0] if ranked else 0,
                rationale=("No complete authoritative catalog match; plan a draft capability.",),
            )
        score, profile = ranked[0]
        item = profile.catalog_item
        if item.availability != "AVAILABLE" or item.configuration_status not in {
            "CONFIGURED",
            "NOT_APPLICABLE",
        }:
            return CapabilityMatch(
                node_id=node.node_id,
                decision="REUSE",
                matched_capability=item,
                score=score,
                rationale=(
                    "Reuse the matching catalog identity after Backend configuration; "
                    "do not create a duplicate.",
                ),
            )
        return CapabilityMatch(
            node_id=node.node_id,
            decision="REUSE",
            matched_capability=item,
            score=score,
            rationale=("Structured authoritative catalog metadata satisfies the responsibility.",),
        )

    @classmethod
    def _score(cls, node: CapabilityNode, profile: CapabilityProfile) -> int:
        item = profile.catalog_item
        score = 0
        if item.capability_id == node.capability_identity:
            score += 100
        if item.capability_id in node.required_capability_ids:
            score += 100
        node_terms = cls._terms(
            " ".join((node.capability_identity, node.responsibility, *node.domain_tags))
        )
        item_terms = cls._terms(
            " ".join((item.capability_id, item.name, item.purpose, *item.keywords))
        )
        score += len(node_terms & item_terms) * 5
        score += len(set(node.input_semantics) & set(profile.input_semantics)) * 10
        score += len(set(node.output_semantics) & set(profile.output_semantics)) * 10
        if set(node.required_tool_ids).issubset(item.backing_tool_ids):
            score += 5
        if set(node.permission_refs).issuperset(item.permission_refs):
            score += 5
        if not item.scope_refs or set(item.scope_refs).issubset(node.scope_refs):
            score += 5
        if set(node.required_skill_ids).issubset(profile.skill_ids):
            score += 5
        return score

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}
