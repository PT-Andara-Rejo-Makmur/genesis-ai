"""Bounded decomposition of understood responsibilities into a capability graph."""

from genesis.control_plane.workforce.graph import CapabilityGraphBuilder
from genesis.control_plane.workforce.models import CapabilityGraph, RequirementUnderstanding


class DecompositionPlanner:
    """Build a maximum Parent -> Sub-Agent -> Sub-Sub-Agent hierarchy by default."""

    def __init__(self, *, max_depth: int = 2) -> None:
        self._builder = CapabilityGraphBuilder(max_depth=max_depth)

    def decompose(self, understanding: RequirementUnderstanding) -> CapabilityGraph:
        return self._builder.build(understanding)

