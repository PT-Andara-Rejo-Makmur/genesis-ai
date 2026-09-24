"""Application service orchestrating internal workforce planning only."""

import hashlib
import json

from genesis.control_plane.factory import CapabilityFactory
from genesis.control_plane.workforce.assurance import WorkforceAssurance
from genesis.control_plane.workforce.composition import CompositionPlanner
from genesis.control_plane.workforce.decomposition import DecompositionPlanner
from genesis.control_plane.workforce.discovery import CapabilityDiscovery
from genesis.control_plane.workforce.graph import CapabilityGraphBuilder
from genesis.control_plane.workforce.interpretation import DeterministicRequirementInterpreter
from genesis.control_plane.workforce.matching import DeterministicCapabilityMatcher
from genesis.control_plane.workforce.models import (
    WorkforcePlan,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)
from genesis.control_plane.workforce.protocols import (
    CapabilityMatcher,
    RequirementInterpreter,
    ResponsibilityDecomposer,
)


class WorkforceFactory:
    """Create a deterministic DRAFT plan; never approve, release, activate, or persist it."""

    def __init__(
        self,
        *,
        capability_factory: CapabilityFactory,
        interpreter: RequirementInterpreter | None = None,
        decomposer: ResponsibilityDecomposer | None = None,
        matcher: CapabilityMatcher | None = None,
        max_depth: int = 2,
    ) -> None:
        self._interpreter = interpreter or DeterministicRequirementInterpreter()
        self._decomposition = decomposer or DecompositionPlanner(max_depth=max_depth)
        self._graph_builder = CapabilityGraphBuilder(max_depth=max_depth)
        self._discovery = CapabilityDiscovery(matcher or DeterministicCapabilityMatcher())
        self._composition = CompositionPlanner(capability_factory=capability_factory)
        self._assurance = WorkforceAssurance()

    async def plan(
        self,
        requirement: WorkforceRequirement,
        registry: WorkforceRegistrySnapshot,
    ) -> WorkforcePlan:
        understanding = await self._interpreter.interpret(requirement)
        self._assurance.validate_understanding(understanding)
        responsibilities = await self._decomposition.decompose(understanding)
        graph = self._graph_builder.build(
            root_identity=understanding.root_identity,
            responsibilities=responsibilities,
        )
        self._assurance.validate_graph(requirement=requirement, graph=graph)
        matches, gaps = self._discovery.discover(graph, registry)
        planned_agents = self._composition.compose(requirement, graph, matches, registry)
        self._assurance.validate(
            requirement=requirement,
            graph=graph,
            planned_agents=planned_agents,
            registry=registry,
        )
        canonical = {
            "requirement": requirement.model_dump(mode="json"),
            "registry": registry.model_dump(mode="json"),
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return WorkforcePlan(
            plan_id=f"workforce_plan_{digest}",
            requirement_understanding=understanding,
            capability_graph=graph,
            capability_gaps=gaps,
            planned_agents=planned_agents,
        )
