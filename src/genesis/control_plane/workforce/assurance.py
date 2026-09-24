"""Fail-closed workforce graph, authority, dependency, and evaluation assurance."""

from __future__ import annotations

from collections import Counter

from genesis.control_plane.workforce.models import (
    AssuranceCode,
    AssuranceFinding,
    CapabilityGraph,
    DependencyKind,
    DependencyStatus,
    EvaluationKind,
    PlannedAgent,
    RequirementUnderstanding,
    WorkforceAssuranceError,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)


class WorkforceAssurance:
    def validate_understanding(self, understanding: RequirementUnderstanding) -> None:
        identities = Counter(item.identity for item in understanding.candidates)
        findings = tuple(
            AssuranceFinding(
                code=AssuranceCode.DUPLICATE_CAPABILITY,
                detail=f"Capability identity appears more than once: {identity}",
            )
            for identity, count in sorted(identities.items())
            if count > 1
        )
        if findings:
            raise WorkforceAssuranceError(findings)

    def validate_graph(
        self,
        *,
        requirement: WorkforceRequirement,
        graph: CapabilityGraph,
    ) -> None:
        findings = (
            *self._graph_findings(graph),
            *self._authority_findings(requirement, graph),
        )
        ordered = tuple(sorted(findings, key=lambda item: (item.code.value, item.node_id or "")))
        if ordered:
            raise WorkforceAssuranceError(ordered)

    def validate(
        self,
        *,
        requirement: WorkforceRequirement,
        graph: CapabilityGraph,
        planned_agents: tuple[PlannedAgent, ...],
        registry: WorkforceRegistrySnapshot,
    ) -> None:
        findings = (
            *self._graph_findings(graph),
            *self._agent_findings(requirement, graph, planned_agents),
            *self._dependency_findings(requirement, planned_agents, registry),
        )
        ordered = tuple(sorted(findings, key=lambda item: (item.code.value, item.node_id or "")))
        if ordered:
            raise WorkforceAssuranceError(ordered)

    def _graph_findings(self, graph: CapabilityGraph) -> tuple[AssuranceFinding, ...]:
        findings: list[AssuranceFinding] = []
        nodes = {item.node_id: item for item in graph.nodes}
        identities = Counter(item.capability_identity for item in graph.nodes)
        findings.extend(
            AssuranceFinding(
                code=AssuranceCode.DUPLICATE_CAPABILITY,
                detail=f"Capability identity appears more than once: {identity}",
            )
            for identity, count in identities.items()
            if count > 1
        )
        roots = [item for item in graph.nodes if item.parent_node_id is None]
        if len(roots) != 1 or not roots or roots[0].node_id != graph.root_node_id:
            findings.append(
                AssuranceFinding(
                    code=AssuranceCode.INVALID_HIERARCHY,
                    detail="Graph must contain exactly one declared root node.",
                )
            )
        children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for node in graph.nodes:
            if node.parent_node_id is not None:
                if node.parent_node_id not in nodes:
                    findings.append(
                        AssuranceFinding(
                            code=AssuranceCode.ORPHAN_NODE,
                            node_id=node.node_id,
                            detail="Parent node does not exist in the graph.",
                        )
                    )
                else:
                    children[node.parent_node_id].append(node.node_id)
                    parent = nodes[node.parent_node_id]
                    if node.depth != parent.depth + 1 or node.depth > graph.max_depth:
                        findings.append(
                            AssuranceFinding(
                                code=AssuranceCode.INVALID_HIERARCHY,
                                node_id=node.node_id,
                                detail="Child depth is not parent depth + 1 or exceeds the limit.",
                            )
                        )
                    if not set(node.domain_tags).issubset(parent.domain_tags):
                        findings.append(
                            AssuranceFinding(
                                code=AssuranceCode.CHILD_BROADER_THAN_PARENT,
                                node_id=node.node_id,
                                detail="Child responsibility dimensions exceed its parent.",
                            )
                        )
                    if not set(node.permission_refs).issubset(parent.permission_refs):
                        findings.append(
                            AssuranceFinding(
                                code=AssuranceCode.CHILD_PERMISSION_EXPANSION,
                                node_id=node.node_id,
                                detail="Child permissions exceed parent permissions.",
                            )
                        )
                    if not set(node.scope_refs).issubset(parent.scope_refs):
                        findings.append(
                            AssuranceFinding(
                                code=AssuranceCode.CHILD_SCOPE_EXPANSION,
                                node_id=node.node_id,
                                detail="Child scopes exceed parent scopes.",
                            )
                        )
        findings.extend(self._cycle_findings(graph, children))
        for node in graph.nodes:
            has_children = bool(children[node.node_id])
            if node.atomic == has_children:
                findings.append(
                    AssuranceFinding(
                        code=AssuranceCode.INVALID_HIERARCHY,
                        node_id=node.node_id,
                        detail=(
                            "Atomic nodes cannot have children and composite nodes "
                            "require children."
                        ),
                    )
                )
        return tuple(findings)

    @staticmethod
    def _cycle_findings(
        graph: CapabilityGraph, children: dict[str, list[str]]
    ) -> tuple[AssuranceFinding, ...]:
        visited: set[str] = set()
        active: set[str] = set()
        cycle_nodes: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in active:
                cycle_nodes.add(node_id)
                return
            if node_id in visited:
                return
            active.add(node_id)
            for child_id in children.get(node_id, []):
                visit(child_id)
            active.remove(node_id)
            visited.add(node_id)

        for node in graph.nodes:
            visit(node.node_id)
        return tuple(
            AssuranceFinding(
                code=AssuranceCode.GRAPH_CYCLE,
                node_id=node_id,
                detail="Capability graph contains a cycle.",
            )
            for node_id in sorted(cycle_nodes)
        )

    @staticmethod
    def _agent_findings(
        requirement: WorkforceRequirement,
        graph: CapabilityGraph,
        agents: tuple[PlannedAgent, ...],
    ) -> tuple[AssuranceFinding, ...]:
        findings: list[AssuranceFinding] = []
        normalized = Counter(" ".join(item.responsibility.casefold().split()) for item in agents)
        findings.extend(
            AssuranceFinding(
                code=AssuranceCode.DUPLICATE_RESPONSIBILITY,
                detail=f"Planned responsibility appears more than once: {responsibility}",
            )
            for responsibility, count in normalized.items()
            if count > 1
        )
        required_evaluations = set(EvaluationKind)
        for agent in agents:
            available = {item.kind for item in agent.evaluation_requirements}
            missing = required_evaluations - available
            if missing:
                findings.append(
                    AssuranceFinding(
                        code=AssuranceCode.MISSING_EVALUATION_COVERAGE,
                        node_id=agent.node_id,
                        detail="Missing evaluation kinds: "
                        + ", ".join(sorted(item.value for item in missing)),
                    )
                )
        if {item.node_id for item in graph.nodes} != {item.node_id for item in agents}:
            findings.append(
                AssuranceFinding(
                    code=AssuranceCode.INVALID_HIERARCHY,
                    detail="Every capability node must have exactly one planned agent.",
                )
            )
        return tuple(findings)

    @staticmethod
    def _authority_findings(
        requirement: WorkforceRequirement,
        graph: CapabilityGraph,
    ) -> tuple[AssuranceFinding, ...]:
        context = requirement.requirement.execution_context
        findings: list[AssuranceFinding] = []
        for node in graph.nodes:
            if not set(node.permission_refs).issubset(context.permission_refs):
                findings.append(
                    AssuranceFinding(
                        code=AssuranceCode.CHILD_PERMISSION_EXPANSION,
                        node_id=node.node_id,
                        detail="Planned permission is absent from Backend execution context.",
                    )
                )
            if not set(node.scope_refs).issubset(context.scope_refs):
                findings.append(
                    AssuranceFinding(
                        code=AssuranceCode.CHILD_SCOPE_EXPANSION,
                        node_id=node.node_id,
                        detail="Planned scope is absent from Backend execution context.",
                    )
                )
        return tuple(findings)

    @staticmethod
    def _dependency_findings(
        requirement: WorkforceRequirement,
        agents: tuple[PlannedAgent, ...],
        registry: WorkforceRegistrySnapshot,
    ) -> tuple[AssuranceFinding, ...]:
        registry_capabilities = {
            item.catalog_item.capability_id for item in registry.capability_profiles
        }
        registry_dependencies = {
            (item.kind, item.dependency_id)
            for item in registry.dependencies
            if item.availability == "AVAILABLE" and item.configuration_status == "CONFIGURED"
        }
        context = requirement.requirement.execution_context
        findings: list[AssuranceFinding] = []
        for agent in agents:
            for dependency in agent.dependency_requirements:
                if dependency.status not in {
                    DependencyStatus.AVAILABLE,
                    DependencyStatus.REUSED,
                }:
                    continue
                valid = True
                if dependency.kind is DependencyKind.CAPABILITY:
                    valid = dependency.dependency_id in registry_capabilities
                elif dependency.kind in {
                    DependencyKind.SKILL,
                    DependencyKind.TOOL,
                    DependencyKind.MODEL_POLICY,
                }:
                    valid = (dependency.kind, dependency.dependency_id) in registry_dependencies
                elif dependency.kind is DependencyKind.PERMISSION:
                    valid = dependency.dependency_id in context.permission_refs
                elif dependency.kind is DependencyKind.SCOPE:
                    valid = dependency.dependency_id in context.scope_refs
                if not valid:
                    findings.append(
                        AssuranceFinding(
                            code=AssuranceCode.INVENTED_AVAILABLE_DEPENDENCY,
                            node_id=agent.node_id,
                            detail=(
                                f"{dependency.kind.value} {dependency.dependency_id} was marked "
                                "available without authoritative evidence."
                            ),
                        )
                    )
        return tuple(findings)
