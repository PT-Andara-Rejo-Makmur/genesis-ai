"""Compose planned agents and canonical drafts through the existing CapabilityFactory."""

from __future__ import annotations

from genesis.capabilities.models import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest
from genesis.control_plane.workforce.evaluation import EvaluationPlanner
from genesis.control_plane.workforce.graph import stable_id
from genesis.control_plane.workforce.models import (
    CapabilityGraph,
    CapabilityMatch,
    DependencyKind,
    DependencyRequirement,
    DependencyStatus,
    PlannedAgent,
    RegistryDependency,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)


class CompositionPlanner:
    def __init__(
        self,
        *,
        capability_factory: CapabilityFactory,
        evaluation_planner: EvaluationPlanner | None = None,
    ) -> None:
        self._capability_factory = capability_factory
        self._evaluation_planner = evaluation_planner or EvaluationPlanner()

    def compose(
        self,
        requirement: WorkforceRequirement,
        graph: CapabilityGraph,
        matches: tuple[CapabilityMatch, ...],
        registry: WorkforceRegistrySnapshot,
    ) -> tuple[PlannedAgent, ...]:
        match_by_node = {item.node_id: item for item in matches}
        agent_ids = {
            node.node_id: stable_id("planned_agent", graph.root_node_id, node.node_id)
            for node in graph.nodes
        }
        agents: list[PlannedAgent] = []
        for node in graph.nodes:
            match = match_by_node[node.node_id]
            dependencies = list(self._dependencies(requirement, node, match, registry))
            if match.decision == "REUSE" and match.matched_capability is not None:
                capability_ref = match.matched_capability.capability_id
                factory_result = None
                ready_state = "READY_FOR_REUSE"
            else:
                execution_context = requirement.requirement.execution_context.model_copy(
                    update={
                        "permission_refs": node.permission_refs,
                        "scope_refs": node.scope_refs,
                    }
                )
                factory_requirement = requirement.requirement.model_copy(
                    update={
                        "execution_context": execution_context,
                        "statement": (
                            "Rancang agent draft untuk tanggung jawab berikut: "
                            f"{node.responsibility}"
                        ),
                        "preferred_capability_type": CapabilityType.AGENT,
                    }
                )
                factory_result = self._capability_factory.analyze(
                    FactoryAnalysisRequest(
                        requirement=factory_requirement,
                        capability_catalog=self._factory_catalog(node, registry),
                    )
                )
                if factory_result.capability_draft is None:
                    raise ValueError("CapabilityFactory did not return a draft for a CREATE plan")
                capability_ref = str(factory_result.capability_draft["capability_id"])
                known_dependencies = {
                    (item.kind, item.dependency_id) for item in dependencies
                }
                dependencies.extend(
                    DependencyRequirement(
                        dependency_id=dependency_id,
                        kind=DependencyKind.CAPABILITY,
                        status=DependencyStatus.MISSING_DEPENDENCY,
                        source="FACTORY",
                        detail="Existing CapabilityFactory reported this capability gap.",
                    )
                    for dependency_id in factory_result.missing_dependencies
                    if (DependencyKind.CAPABILITY, dependency_id) not in known_dependencies
                )
                ready_state = "READY_FOR_DRAFT"
            ordered_dependencies = tuple(
                sorted(dependencies, key=lambda item: (item.kind.value, item.dependency_id))
            )
            blocked = any(
                item.status
                in {DependencyStatus.MISSING_DEPENDENCY, DependencyStatus.NEEDS_CONFIGURATION}
                for item in ordered_dependencies
            )
            readiness = "NEEDS_CONFIGURATION" if blocked else ready_state
            agents.append(
                PlannedAgent(
                    planned_agent_id=agent_ids[node.node_id],
                    node_id=node.node_id,
                    parent_agent_id=(
                        agent_ids.get(node.parent_node_id)
                        if node.parent_node_id is not None
                        else None
                    ),
                    responsibility=node.responsibility,
                    capability_decision=match.decision,
                    capability_ref=capability_ref,
                    dependency_requirements=ordered_dependencies,
                    model_policy_ref=requirement.model_policy_ref,
                    budget_policy=requirement.budget_policy,
                    delegation_policy=requirement.delegation_policy,
                    evidence_requirements=requirement.evidence_requirements,
                    evaluation_requirements=self._evaluation_planner.plan(node),
                    readiness=readiness,
                    factory_result=factory_result,
                )
            )
        return tuple(agents)

    @staticmethod
    def _factory_catalog(
        node: object,
        registry: WorkforceRegistrySnapshot,
    ) -> tuple[CapabilityCatalogItem, ...]:
        """Project only relevant authoritative catalog entries into CapabilityFactory.

        Workforce matching and unit-level capability resolution remain separate.  The
        latter still needs the Backend snapshot to reuse tool-backed capabilities when
        it builds a canonical draft; omitting it made otherwise available dependencies
        disappear at the factory boundary.
        """
        from genesis.control_plane.workforce.models import CapabilityNode

        if not isinstance(node, CapabilityNode):
            raise TypeError("node must be a CapabilityNode")
        required = set(node.required_tool_ids) | set(node.required_capability_ids)
        return tuple(
            profile.catalog_item
            for profile in registry.capability_profiles
            if profile.catalog_item.capability_id in required
            or required.intersection(profile.catalog_item.backing_tool_ids)
        )

    @classmethod
    def _dependencies(
        cls,
        requirement: WorkforceRequirement,
        node: object,
        match: CapabilityMatch,
        registry: WorkforceRegistrySnapshot,
    ) -> tuple[DependencyRequirement, ...]:
        from genesis.control_plane.workforce.models import CapabilityNode

        if not isinstance(node, CapabilityNode):
            raise TypeError("node must be a CapabilityNode")
        dependencies: list[DependencyRequirement] = []
        if match.decision == "REUSE" and match.matched_capability is not None:
            capability_status = (
                DependencyStatus.REUSED
                if match.matched_capability.availability == "AVAILABLE"
                and match.matched_capability.configuration_status
                in {"CONFIGURED", "NOT_APPLICABLE"}
                else DependencyStatus.NEEDS_CONFIGURATION
            )
            dependencies.append(
                DependencyRequirement(
                    dependency_id=match.matched_capability.capability_id,
                    kind=DependencyKind.CAPABILITY,
                    status=capability_status,
                    source="REGISTRY",
                    detail=(
                        "Reused from the authoritative registry snapshot."
                        if capability_status is DependencyStatus.REUSED
                        else "Existing capability requires Backend configuration before use."
                    ),
                )
            )
        else:
            if match.matched_capability is not None:
                dependencies.append(
                    DependencyRequirement(
                        dependency_id=match.matched_capability.capability_id,
                        kind=DependencyKind.CAPABILITY,
                        status=DependencyStatus.NEEDS_CONFIGURATION,
                        source="REGISTRY",
                        detail=(
                            "Matching registry capability is unavailable or requires "
                            "Backend configuration."
                        ),
                    )
                )
            dependencies.extend(
                DependencyRequirement(
                    dependency_id=capability_id,
                    kind=DependencyKind.CAPABILITY,
                    status=DependencyStatus.MISSING_DEPENDENCY,
                    source="REQUIREMENT",
                    detail="No reusable catalog capability satisfies this requirement.",
                )
                for capability_id in node.required_capability_ids
            )
        dependencies.extend(
            cls._registry_dependency(dependency_id, DependencyKind.SKILL, registry.dependencies)
            for dependency_id in node.required_skill_ids
        )
        dependencies.extend(
            cls._registry_dependency(dependency_id, DependencyKind.TOOL, registry.dependencies)
            for dependency_id in node.required_tool_ids
        )
        dependencies.extend(
            DependencyRequirement(
                dependency_id=permission,
                kind=DependencyKind.PERMISSION,
                status=DependencyStatus.AVAILABLE,
                source="AUTHORITY_CONTEXT",
                detail="Permission is present in the Backend-supplied execution context.",
            )
            for permission in node.permission_refs
        )
        dependencies.extend(
            DependencyRequirement(
                dependency_id=scope,
                kind=DependencyKind.SCOPE,
                status=DependencyStatus.AVAILABLE,
                source="AUTHORITY_CONTEXT",
                detail="Scope is present in the Backend-supplied execution context.",
            )
            for scope in node.scope_refs
        )
        if requirement.model_policy_ref is not None:
            dependencies.append(
                cls._registry_dependency(
                    requirement.model_policy_ref,
                    DependencyKind.MODEL_POLICY,
                    registry.dependencies,
                )
            )
        if requirement.budget_policy is not None:
            dependencies.append(
                DependencyRequirement(
                    dependency_id="execution-budget",
                    kind=DependencyKind.BUDGET_POLICY,
                    status=DependencyStatus.AVAILABLE,
                    source="REQUIREMENT",
                    detail="Budget limit is explicitly supplied by the requirement.",
                )
            )
        dependencies.append(
            DependencyRequirement(
                dependency_id="delegation-policy",
                kind=DependencyKind.DELEGATION_POLICY,
                status=DependencyStatus.AVAILABLE,
                source="REQUIREMENT",
                detail="Delegation remains bounded by the explicit planning policy.",
            )
        )
        dependencies.extend(
            DependencyRequirement(
                dependency_id=stable_id("evidence", item),
                kind=DependencyKind.EVIDENCE,
                status=DependencyStatus.AVAILABLE,
                source="REQUIREMENT",
                detail=item,
            )
            for item in requirement.evidence_requirements
        )
        return tuple(sorted(dependencies, key=lambda item: (item.kind.value, item.dependency_id)))

    @staticmethod
    def _registry_dependency(
        dependency_id: str,
        kind: DependencyKind,
        registry_dependencies: tuple[RegistryDependency, ...],
    ) -> DependencyRequirement:
        item = next(
            (
                candidate
                for candidate in registry_dependencies
                if candidate.dependency_id == dependency_id and candidate.kind == kind
            ),
            None,
        )
        if item is None or item.availability != "AVAILABLE":
            status = DependencyStatus.MISSING_DEPENDENCY
            detail = "Required dependency is absent from the authoritative registry snapshot."
            source = "REQUIREMENT"
        elif item.configuration_status == "NEEDS_CONFIGURATION":
            status = DependencyStatus.NEEDS_CONFIGURATION
            detail = "Registry dependency exists but requires Backend configuration."
            source = "REGISTRY"
        else:
            status = DependencyStatus.REUSED
            detail = "Dependency is reused from the authoritative registry snapshot."
            source = "REGISTRY"
        return DependencyRequirement(
            dependency_id=dependency_id,
            kind=kind,
            status=status,
            source=source,
            detail=detail,
        )
