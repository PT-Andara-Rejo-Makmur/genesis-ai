"""Capability discovery using an immutable Backend registry snapshot."""

from collections.abc import Sequence

from genesis.control_plane.workforce.models import (
    CapabilityGap,
    CapabilityGraph,
    CapabilityMatch,
    WorkforceRegistrySnapshot,
)
from genesis.control_plane.workforce.protocols import CapabilityMatcher


class CapabilityDiscovery:
    def __init__(self, matcher: CapabilityMatcher) -> None:
        self._matcher = matcher

    def discover(
        self, graph: CapabilityGraph, registry: WorkforceRegistrySnapshot
    ) -> tuple[tuple[CapabilityMatch, ...], tuple[CapabilityGap, ...]]:
        matches: list[CapabilityMatch] = []
        gaps: list[CapabilityGap] = []
        reused: list[str] = []
        for node in graph.nodes:
            match = self._matcher.match(
                node,
                registry,
                excluded_capability_ids=tuple(reused),
            )
            matches.append(match)
            if match.decision == "REUSE" and match.matched_capability is not None:
                reused.append(match.matched_capability.capability_id)
            else:
                gaps.append(
                    CapabilityGap(
                        node_id=node.node_id,
                        capability_identity=node.capability_identity,
                        reason=match.rationale[0],
                    )
                )
        return tuple(matches), tuple(gaps)


def matched_ids(matches: Sequence[CapabilityMatch]) -> tuple[str, ...]:
    return tuple(
        item.matched_capability.capability_id
        for item in matches
        if item.decision == "REUSE" and item.matched_capability is not None
    )

