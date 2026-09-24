from pathlib import Path

import pytest

from genesis.capabilities import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryRequirement
from genesis.control_plane.workforce import (
    AssuranceCode,
    CapabilityProfile,
    DependencyKind,
    DependencyStatus,
    RegistryDependency,
    ResponsibilityRequirement,
    WorkforceAssurance,
    WorkforceAssuranceError,
    WorkforceFactory,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)
from genesis.runtime.limits import ExecutionBudget

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def factory_requirement(statement: str) -> FactoryRequirement:
    return FactoryRequirement.model_validate(
        {
            "execution_context": {
                "tenant_id": "tenant_workforce",
                "organization_id": "organization_workforce",
                "workspace_id": "workspace_workforce",
                "actor_id": "actor_workforce",
                "authority_context": {
                    "role": "REQUESTER",
                    "authority_level": "REQUESTER",
                },
                "permission_refs": ["vendor.read"],
                "scope_refs": ["scope.project.vendor"],
                "data_classification": "INTERNAL",
                "correlation_id": "corr_workforce_001",
            },
            "statement": statement,
        }
    )


def workforce_factory() -> WorkforceFactory:
    capability_factory = CapabilityFactory(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    return WorkforceFactory(capability_factory=capability_factory)


def vendor_requirement(statement: str | None = None) -> WorkforceRequirement:
    return WorkforceRequirement(
        requirement=factory_requirement(
            statement
            or (
                "Coordinate vendor performance with schedule monitoring, quality monitoring "
                "covering material compliance and defect detection, and vendor risk analysis."
            )
        ),
        required_skill_ids=("skill.vendor-analysis",),
        required_tool_ids=("vendor.transactions.read",),
        model_policy_ref="model-policy.standard-v1",
        budget_policy=ExecutionBudget(
            max_tokens=4_000,
            max_steps=8,
            max_tool_calls=12,
            max_children=8,
            max_depth=2,
        ),
    )


def registry() -> WorkforceRegistrySnapshot:
    return WorkforceRegistrySnapshot(
        capability_profiles=(
            CapabilityProfile(
                catalog_item=CapabilityCatalogItem(
                    capability_id="vendor.performance",
                    version="1.0.0",
                    name="Vendor performance coordination",
                    purpose="Coordinate vendor performance evidence for human review",
                    capability_type=CapabilityType.AGENT,
                    permission_refs=("vendor.read",),
                    scope_refs=("scope.project.vendor",),
                    keywords=("vendor", "performance"),
                ),
                input_semantics=("business requirement",),
                output_semantics=("reviewable workforce result",),
                skill_ids=("skill.vendor-analysis",),
            ),
        ),
        dependencies=(
            RegistryDependency(
                dependency_id="skill.vendor-analysis",
                kind=DependencyKind.SKILL,
            ),
            RegistryDependency(
                dependency_id="model-policy.standard-v1",
                kind=DependencyKind.MODEL_POLICY,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_workforce_factory_builds_parent_sub_and_sub_sub_drafts() -> None:
    plan = await workforce_factory().plan(vendor_requirement(), registry())

    nodes = {item.capability_identity: item for item in plan.capability_graph.nodes}
    assert tuple(nodes) == (
        "vendor.performance",
        "quality.monitoring",
        "schedule.monitoring",
        "vendor.risk.analysis",
        "defect.detection",
        "material.compliance",
    )
    assert nodes["vendor.performance"].depth == 0
    assert nodes["quality.monitoring"].depth == 1
    assert nodes["material.compliance"].depth == 2
    assert nodes["material.compliance"].parent_node_id == nodes["quality.monitoring"].node_id
    assert nodes["defect.detection"].parent_node_id == nodes["quality.monitoring"].node_id

    agents = {item.node_id: item for item in plan.planned_agents}
    root_agent = agents[nodes["vendor.performance"].node_id]
    assert root_agent.capability_decision == "REUSE"
    assert root_agent.capability_ref == "vendor.performance"
    assert root_agent.factory_result is None
    assert root_agent.readiness == "NEEDS_CONFIGURATION"

    missing_tool = next(
        item
        for item in root_agent.dependency_requirements
        if item.dependency_id == "vendor.transactions.read"
    )
    reused_skill = next(
        item
        for item in root_agent.dependency_requirements
        if item.dependency_id == "skill.vendor-analysis"
    )
    assert missing_tool.status is DependencyStatus.MISSING_DEPENDENCY
    assert reused_skill.status is DependencyStatus.REUSED
    assert len(plan.canonical_agent_drafts()) == 5
    assert all(item["lifecycle_state"] == "DRAFT" for item in plan.canonical_agent_drafts())
    created = next(
        item for item in plan.planned_agents if item.capability_decision == "CREATE"
    )
    assert created.readiness == "NEEDS_CONFIGURATION"
    assert any(
        item.source == "FACTORY" and item.status is DependencyStatus.MISSING_DEPENDENCY
        for item in created.dependency_requirements
    )
    assert plan.lifecycle_state == "DRAFT"
    assert plan.authoritative_state_changed is False


@pytest.mark.asyncio
async def test_same_requirement_and_registry_produce_identical_plan() -> None:
    service = workforce_factory()
    first = await service.plan(vendor_requirement(), registry())
    second = await service.plan(vendor_requirement(), registry())

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


@pytest.mark.asyncio
async def test_repeated_requirement_phrases_do_not_duplicate_planned_agents() -> None:
    repeated = vendor_requirement(
        "Coordinate vendor performance with schedule monitoring and schedule monitoring, "
        "quality monitoring with material compliance, material compliance, defect detection, "
        "and vendor risk analysis."
    )
    plan = await workforce_factory().plan(repeated, registry())

    identities = [item.capability_identity for item in plan.capability_graph.nodes]
    responsibilities = [item.responsibility for item in plan.planned_agents]
    assert len(identities) == len(set(identities))
    assert len(responsibilities) == len(set(responsibilities))


@pytest.mark.asyncio
async def test_unavailable_registry_dependency_never_looks_ready() -> None:
    unavailable = registry().model_copy(
        update={
            "dependencies": (
                RegistryDependency(
                    dependency_id="skill.vendor-analysis",
                    kind=DependencyKind.SKILL,
                    availability="UNAVAILABLE",
                ),
                RegistryDependency(
                    dependency_id="vendor.transactions.read",
                    kind=DependencyKind.TOOL,
                    configuration_status="NEEDS_CONFIGURATION",
                ),
                RegistryDependency(
                    dependency_id="model-policy.standard-v1",
                    kind=DependencyKind.MODEL_POLICY,
                ),
            )
        }
    )
    plan = await workforce_factory().plan(vendor_requirement(), unavailable)
    root = plan.planned_agents[0]
    statuses = {
        item.dependency_id: item.status for item in root.dependency_requirements
    }

    assert statuses["skill.vendor-analysis"] is DependencyStatus.MISSING_DEPENDENCY
    assert statuses["vendor.transactions.read"] is DependencyStatus.NEEDS_CONFIGURATION
    assert root.readiness == "NEEDS_CONFIGURATION"


@pytest.mark.asyncio
async def test_unconfigured_existing_capability_is_reused_without_duplicate_draft() -> None:
    snapshot = registry()
    profile = snapshot.capability_profiles[0]
    unconfigured_item = profile.catalog_item.model_copy(
        update={"configuration_status": "NEEDS_CONFIGURATION"}
    )
    unconfigured = snapshot.model_copy(
        update={
            "capability_profiles": (
                profile.model_copy(update={"catalog_item": unconfigured_item}),
            )
        }
    )

    plan = await workforce_factory().plan(vendor_requirement(), unconfigured)
    root = plan.planned_agents[0]
    capability_dependency = next(
        item
        for item in root.dependency_requirements
        if item.kind is DependencyKind.CAPABILITY
    )

    assert root.capability_decision == "REUSE"
    assert root.factory_result is None
    assert capability_dependency.status is DependencyStatus.NEEDS_CONFIGURATION
    assert root.readiness == "NEEDS_CONFIGURATION"


@pytest.mark.asyncio
async def test_duplicate_structured_capability_identity_is_rejected() -> None:
    duplicate = WorkforceRequirement(
        requirement=factory_requirement("Plan one governed duplicate responsibility safely."),
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="duplicate.analysis",
                purpose="Analyze supplied evidence.",
                input_semantics=("evidence",),
                output_semantics=("finding",),
                domain_tags=("analysis",),
            ),
            ResponsibilityRequirement(
                identity="duplicate.analysis",
                purpose="Analyze the same supplied evidence again.",
                input_semantics=("evidence",),
                output_semantics=("finding",),
                domain_tags=("analysis",),
            ),
        ),
    )

    with pytest.raises(WorkforceAssuranceError) as error:
        await workforce_factory().plan(duplicate, WorkforceRegistrySnapshot())

    assert {item.code for item in error.value.findings} == {
        AssuranceCode.DUPLICATE_CAPABILITY
    }


@pytest.mark.asyncio
async def test_cyclic_decomposition_is_rejected() -> None:
    cyclic = WorkforceRequirement(
        requirement=factory_requirement("Plan a governed cyclic responsibility example safely."),
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="cycle.alpha",
                parent_identity="cycle.charlie",
                purpose="Alpha responsibility.",
                domain_tags=("cycle",),
            ),
            ResponsibilityRequirement(
                identity="cycle.bravo",
                parent_identity="cycle.alpha",
                purpose="Bravo responsibility.",
                domain_tags=("cycle",),
            ),
            ResponsibilityRequirement(
                identity="cycle.charlie",
                parent_identity="cycle.bravo",
                purpose="Charlie responsibility.",
                domain_tags=("cycle",),
            ),
        ),
    )

    with pytest.raises(WorkforceAssuranceError) as error:
        await workforce_factory().plan(cyclic, WorkforceRegistrySnapshot())

    assert AssuranceCode.GRAPH_CYCLE in {item.code for item in error.value.findings}


@pytest.mark.asyncio
async def test_orphan_decomposition_is_rejected() -> None:
    orphan = WorkforceRequirement(
        requirement=factory_requirement("Plan one governed orphan responsibility safely."),
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="root.analysis",
                purpose="Root responsibility.",
                atomic=False,
                domain_tags=("analysis",),
            ),
            ResponsibilityRequirement(
                identity="child.analysis",
                parent_identity="missing.analysis",
                purpose="Orphan child responsibility.",
                domain_tags=("analysis",),
            ),
        ),
    )

    with pytest.raises(WorkforceAssuranceError) as error:
        await workforce_factory().plan(orphan, WorkforceRegistrySnapshot())

    assert AssuranceCode.ORPHAN_NODE in {item.code for item in error.value.findings}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("root_permissions", "root_scopes", "child_permissions", "child_scopes", "code"),
    (
        (
            (),
            ("scope.project.vendor",),
            ("vendor.read",),
            ("scope.project.vendor",),
            AssuranceCode.CHILD_PERMISSION_EXPANSION,
        ),
        (
            ("vendor.read",),
            ("scope.project.vendor",),
            ("vendor.read",),
            ("scope.project.other",),
            AssuranceCode.CHILD_SCOPE_EXPANSION,
        ),
    ),
)
async def test_child_authority_expansion_is_rejected(
    root_permissions: tuple[str, ...],
    root_scopes: tuple[str, ...],
    child_permissions: tuple[str, ...],
    child_scopes: tuple[str, ...],
    code: AssuranceCode,
) -> None:
    requirement = WorkforceRequirement(
        requirement=factory_requirement("Plan one parent and child responsibility safely."),
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="parent.analysis",
                purpose="Coordinate bounded analysis.",
                atomic=False,
                domain_tags=("analysis",),
                permission_refs=root_permissions,
                scope_refs=root_scopes,
            ),
            ResponsibilityRequirement(
                identity="child.analysis",
                parent_identity="parent.analysis",
                purpose="Perform bounded analysis.",
                domain_tags=("analysis",),
                permission_refs=child_permissions,
                scope_refs=child_scopes,
            ),
        ),
    )

    with pytest.raises(WorkforceAssuranceError) as error:
        await workforce_factory().plan(requirement, WorkforceRegistrySnapshot())

    assert code in {item.code for item in error.value.findings}


@pytest.mark.asyncio
async def test_child_responsibility_cannot_be_broader_than_parent() -> None:
    requirement = WorkforceRequirement(
        requirement=factory_requirement("Plan a bounded parent and child analysis safely."),
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="parent.analysis",
                purpose="Coordinate bounded analysis.",
                atomic=False,
                domain_tags=("analysis",),
            ),
            ResponsibilityRequirement(
                identity="child.analysis",
                parent_identity="parent.analysis",
                purpose="Perform analysis plus unrelated finance work.",
                domain_tags=("analysis", "finance"),
            ),
        ),
    )

    with pytest.raises(WorkforceAssuranceError) as error:
        await workforce_factory().plan(requirement, WorkforceRegistrySnapshot())

    assert AssuranceCode.CHILD_BROADER_THAN_PARENT in {
        item.code for item in error.value.findings
    }


@pytest.mark.asyncio
async def test_missing_evaluation_coverage_is_rejected() -> None:
    requirement = vendor_requirement()
    snapshot = registry()
    plan = await workforce_factory().plan(requirement, snapshot)
    first = plan.planned_agents[0]
    incomplete = first.model_copy(
        update={"evaluation_requirements": first.evaluation_requirements[:-1]}
    )
    agents = (incomplete, *plan.planned_agents[1:])

    with pytest.raises(WorkforceAssuranceError) as error:
        WorkforceAssurance().validate(
            requirement=requirement,
            graph=plan.capability_graph,
            planned_agents=agents,
            registry=snapshot,
        )

    assert AssuranceCode.MISSING_EVALUATION_COVERAGE in {
        item.code for item in error.value.findings
    }
