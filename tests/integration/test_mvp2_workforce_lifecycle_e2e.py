from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alos.agents.lifecycle import AgentRunAuthority, AuthoritativeRunStatus
from alos.agents.registry import AgentRegistry
from alos.agents.runtime import AuthoritativeRuntimeOrchestrator
from alos.audit import InMemoryAuditRepository
from alos.config import Settings as BackendSettings
from alos.contracts import CanonicalContractCatalog as BackendContracts
from alos.governance.gates import (
    AssuranceEvaluator,
    AutomatedAssuranceReport,
    ExpectedBehavior,
    ObservedBehavior,
    TestCategory,
)
from alos.governance.materiality import Materiality
from alos.identity import Principal
from alos.integrations.genesis import GenesisClient
from alos.main import create_app as create_backend_app
from alos.observability.correlation import correlation_id_context
from alos.registry import DecisionAuthority, RegistryState
from alos.releases import InMemoryReleaseAuthority, ReleaseConflictError, ReleaseState
from alos.reviews.decisions import AuthoritativeDecision, AuthorityLevel, DecisionOutcome
from alos.reviews.packages import ReviewPackageReference
from pydantic import SecretStr

from genesis.capabilities import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem
from genesis.config import Settings as GenesisSettings
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryRequirement
from genesis.control_plane.workforce import (
    CapabilityProfile,
    DependencyKind,
    DependencyStatus,
    RegistryDependency,
    ResponsibilityRequirement,
    WorkforceFactory,
    WorkforceRegistrySnapshot,
    WorkforceRequirement,
)
from genesis.main import create_app as create_genesis_app

WORKSPACE = Path(__file__).resolve().parents[3]
CONTRACTS_ROOT = WORKSPACE / "alos-contracts"
TOKEN = "-".join(("mvp2", "integration", "token"))


def workforce_requirement() -> WorkforceRequirement:
    requirement = FactoryRequirement.model_validate(
        {
            "execution_context": {
                "tenant_id": "tenant_mvp2",
                "organization_id": "org_mvp2",
                "workspace_id": "workspace_mvp2",
                "actor_id": "actor_mvp2",
                "authority_context": {"role": "REQUESTER", "authority_level": "REQUESTER"},
                "permission_refs": ["tools.diagnostic.execute"],
                "scope_refs": ["scope.diagnostic"],
                "data_classification": "INTERNAL",
                "correlation_id": "corr_mvp2_e2e",
            },
            "statement": (
                "Coordinate diagnostic operations, monitor one diagnostic task, and execute "
                "a bounded diagnostic task with evidence for human review."
            ),
        }
    )
    authority = {
        "permission_refs": ("tools.diagnostic.execute",),
        "scope_refs": ("scope.diagnostic",),
    }
    return WorkforceRequirement(
        requirement=requirement,
        responsibility_hints=(
            ResponsibilityRequirement(
                identity="diagnostic.operations",
                purpose="Coordinate bounded diagnostic operations.",
                atomic=False,
                domain_tags=("diagnostic", "operations"),
                **authority,
            ),
            ResponsibilityRequirement(
                identity="diagnostic.monitoring",
                parent_identity="diagnostic.operations",
                purpose="Monitor diagnostic tasks.",
                atomic=False,
                domain_tags=("diagnostic", "operations"),
                **authority,
            ),
            ResponsibilityRequirement(
                identity="diagnostic.task",
                parent_identity="diagnostic.monitoring",
                purpose="Execute one bounded diagnostic task.",
                required_tool_ids=("diagnostic.echo",),
                domain_tags=("diagnostic", "operations"),
                **authority,
            ),
        ),
        model_policy_ref="model-policy.standard-v1",
    )


def workforce_registry() -> WorkforceRegistrySnapshot:
    return WorkforceRegistrySnapshot(
        capability_profiles=(
            CapabilityProfile(
                catalog_item=CapabilityCatalogItem(
                    capability_id="diagnostic.operations",
                    version="1.0.0",
                    name="Diagnostic operations",
                    purpose="Coordinate bounded diagnostic operations.",
                    capability_type=CapabilityType.AGENT,
                    permission_refs=("tools.diagnostic.execute",),
                    scope_refs=("scope.diagnostic",),
                )
            ),
            CapabilityProfile(
                catalog_item=CapabilityCatalogItem(
                    capability_id="task.read",
                    version="1.0.0",
                    name="Task read",
                    purpose="Read a task through the Backend ToolExecutor.",
                    capability_type=CapabilityType.TOOL_REQUIREMENT,
                    backing_tool_ids=("diagnostic.echo",),
                    permission_refs=("tools.diagnostic.execute",),
                    scope_refs=("scope.diagnostic",),
                    keywords=("task", "read"),
                )
            ),
        ),
        dependencies=(
            RegistryDependency(dependency_id="diagnostic.echo", kind=DependencyKind.TOOL),
            RegistryDependency(
                dependency_id="model-policy.standard-v1",
                kind=DependencyKind.MODEL_POLICY,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_mvp2_factory_governance_runtime_tool_and_audit_e2e() -> None:
    genesis_contracts = CanonicalContractCatalog(CONTRACTS_ROOT)
    plan = await WorkforceFactory(
        capability_factory=CapabilityFactory(contracts=genesis_contracts)
    ).plan(workforce_requirement(), workforce_registry())
    assert [node.depth for node in plan.capability_graph.nodes] == [0, 1, 2]
    assert plan.planned_agents[0].capability_decision == "REUSE"
    leaf = plan.planned_agents[-1]
    assert leaf.capability_decision == "CREATE"
    assert any(
        dependency.status is DependencyStatus.MISSING_DEPENDENCY
        for dependency in leaf.dependency_requirements
    )
    assert leaf.factory_result is not None
    draft = leaf.factory_result.agent_draft
    assert draft is not None
    assert draft.lifecycle_state == "DRAFT"
    definition = draft.agent_definition
    assert definition["permission_refs"] == ["tools.diagnostic.execute"]
    assert definition["scope_refs"] == ["scope.diagnostic"]

    backend_contracts = BackendContracts(CONTRACTS_ROOT)
    audit = InMemoryAuditRepository()
    registry = AgentRegistry(backend_contracts, audit)
    governed_definition = {**definition, "approval_required": False}
    entry = await registry.register(
        governed_definition,
        tenant_id="tenant_mvp2",
        organization_id="org_mvp2",
        workspace_id="workspace_mvp2",
        actor_id="actor_mvp2",
        correlation_id="corr_mvp2_e2e",
    )
    assert entry.state is RegistryState.DRAFT

    principal = Principal(
        actor_id="actor_mvp2",
        tenant_id="tenant_mvp2",
        organization_id="org_mvp2",
        workspace_id="workspace_mvp2",
        permissions=frozenset({"tools.diagnostic.execute"}),
        scopes=frozenset({"scope.diagnostic"}),
        roles=frozenset({"diagnostic_runner"}),
    )
    authority = AgentRunAuthority(contracts=backend_contracts, audit=audit)
    backend_app = create_backend_app(
        BackendSettings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL="postgresql+asyncpg://alos:alos@localhost:5432/alos_test",
            GENESIS_BASE_URL="http://genesis.test",
            GENESIS_INTERNAL_TOKEN=TOKEN,
            ALOS_CONTRACTS_PATH=CONTRACTS_ROOT,
            ENABLE_TEST_TOOLS=True,
        )
    )
    backend_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend_app), base_url="http://backend.test"
    )
    backend_app.state.agent_run_authority = authority
    genesis_app = create_genesis_app(
        GenesisSettings(
            _env_file=None,
            APP_ENV="test",
            ALOS_BACKEND_BASE_URL="http://backend.test",
            ALOS_INTERNAL_TOKEN=TOKEN,
            ALOS_CONTRACTS_PATH=CONTRACTS_ROOT,
            ENABLE_TEST_RUNTIME=True,
        )
    )
    genesis_app.state.backend_http_client = backend_client
    genesis_http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=genesis_app), base_url="http://genesis.test"
    )
    genesis_client = GenesisClient(
        base_url="http://genesis.test",
        internal_token=SecretStr(TOKEN),
        client=genesis_http,
    )
    orchestrator = AuthoritativeRuntimeOrchestrator(authority=authority, genesis=genesis_client)
    payload = {
        "capability_id": definition["capability_ids"][0],
        "input": {"workspace_id": "workspace_mvp2", "request": "echo governed proof"},
        "requested_tool_ids": ["diagnostic.echo"],
        "scope_refs": ["scope.diagnostic"],
        "execution_budget": {"max_tokens": 100, "max_steps": 3, "max_tool_calls": 1},
        "execution_mode": "TEST",
    }
    token = correlation_id_context.set("corr_mvp2_e2e")
    try:
        with pytest.raises(ValueError, match="not ACTIVE"):
            await orchestrator.execute(
                payload, principal=principal, agent=entry, test_mode_allowed=True
            )
        entry = await registry.approve(
            tenant_id=entry.tenant_id,
            workspace_id=entry.workspace_id,
            subject_id=entry.subject_id,
            version=entry.version,
            actor_id="actor_it_mvp2",
            decision_id="decision_mvp2_human",
            authority=DecisionAuthority.IT,
            correlation_id="corr_mvp2_e2e",
        )
        entry = await registry.activate(
            tenant_id=entry.tenant_id,
            workspace_id=entry.workspace_id,
            subject_id=entry.subject_id,
            version=entry.version,
            actor_id="actor_release_mvp2",
            release_id="release_mvp2",
            correlation_id="corr_mvp2_e2e",
        )
        completed = await orchestrator.execute(
            payload, principal=principal, agent=entry, test_mode_allowed=True
        )
    finally:
        correlation_id_context.reset(token)
        await genesis_http.aclose()
        await backend_client.aclose()

    assert completed.status is AuthoritativeRunStatus.COMPLETED, (
        completed.error_code,
        completed.error_message,
        completed.result.get("error") if completed.result else None,
        completed.result.get("tool_results") if completed.result else None,
    )
    assert completed.root_run_id == completed.run_id
    assert completed.correlation_id == "corr_mvp2_e2e"
    assert completed.usage_ref == f"urn:alos:usage:{completed.run_id}"
    assert completed.total_tokens == 6
    steps = await authority.list_steps(completed.run_id)
    assert len(steps) == 1 and steps[0].tool_id == "diagnostic.echo"
    assert [record.outcome for record in backend_app.state.tool_audit_sink.records] == [
        "REQUESTED",
        "SUCCESS",
    ]
    events = audit.list_events(tenant_id="tenant_mvp2")
    expected_events = {
        "registry.version.created",
        "registry.version.approved",
        "registry.version.activated",
        "run.started",
        "run.completed",
    }
    assert expected_events.issubset(
        {event.event_type for event in events}
    )


@pytest.mark.asyncio
async def test_backend_cancellation_is_authoritative_and_audited() -> None:
    contracts = BackendContracts(CONTRACTS_ROOT)
    audit = InMemoryAuditRepository()
    authority = AgentRunAuthority(contracts=contracts, audit=audit, allow_test_drafts=True)
    registry = AgentRegistry(contracts, audit)
    definition = {
        "tenant_id": "tenant_mvp2",
        "organization_id": "org_mvp2",
        "workspace_id": "workspace_mvp2",
        "agent_id": "agent.mvp2.cancel",
        "agent_version": "1.0.0",
        "owner_actor_id": "actor_mvp2",
        "name": "Cancellation proof",
        "purpose": "Prove Backend-owned cancellation and safe failure.",
        "risk_level": "LOW",
        "capability_ids": ["capability.mvp2.cancel"],
        "skill_refs": [],
        "model_policy_ref": "policy.runtime-test",
        "tool_ids": [],
        "permission_refs": [],
        "scope_refs": ["scope.diagnostic"],
        "delegation_policy": {"enabled": False, "max_depth": 0},
    }
    draft = await registry.register(
        definition,
        tenant_id="tenant_mvp2",
        organization_id="org_mvp2",
        workspace_id="workspace_mvp2",
        actor_id="actor_mvp2",
        correlation_id="corr_mvp2_cancel",
    )
    started = await authority.begin(
        {
            "run_id": "run_mvp2_cancel",
            "root_run_id": "run_mvp2_cancel",
            "agent_id": draft.subject_id,
            "agent_version": draft.version,
            "capability_id": "capability.mvp2.cancel",
            "execution_context": {
                "tenant_id": "tenant_mvp2",
                "organization_id": "org_mvp2",
                "workspace_id": "workspace_mvp2",
                "actor_id": "actor_mvp2",
                "authority_context": {"role": "REQUESTER"},
                "permission_refs": [],
                "scope_refs": ["scope.diagnostic"],
                "data_classification": "INTERNAL",
                "correlation_id": "corr_mvp2_cancel",
                "execution_budget": {"max_tokens": 10, "max_steps": 1},
            },
            "input": {},
            "requested_tool_ids": [],
            "execution_mode": "TEST",
        },
        agent=draft,
    )
    requested = await authority.request_cancel(
        started.run_id,
        actor_id="actor_it_mvp2",
        reason="Human requested safe cancellation.",
        correlation_id="corr_mvp2_cancel",
    )
    cancelled = await authority.cancel(
        started.run_id,
        actor_id="actor_it_mvp2",
        reason="Cancellation acknowledged.",
        correlation_id="corr_mvp2_cancel",
    )
    assert requested.status is AuthoritativeRunStatus.CANCEL_REQUESTED
    assert cancelled.status is AuthoritativeRunStatus.CANCELLED
    assert cancelled.error_code == "RUN_CANCELLED"
    assert {"run.cancel_requested", "run.cancelled"}.issubset(
        {event.event_type for event in audit.list_events(tenant_id="tenant_mvp2")}
    )


@pytest.mark.asyncio
async def test_ai_review_is_advisory_and_returned_release_cannot_activate() -> None:
    audit = InMemoryAuditRepository()
    authority = InMemoryReleaseAuthority(audit)
    release_id = "release_mvp2_returned"
    review_id = "review_mvp2_returned"
    await authority.create(
        release_id=release_id,
        review_id=review_id,
        tenant_id="tenant_mvp2",
        organization_id="org_mvp2",
        workspace_id="workspace_mvp2",
        subject_id="agent.mvp2.returned",
        subject_version="1.0.0",
        materiality=Materiality.NON_MATERIAL,
        actor_id="actor_maker_mvp2",
        correlation_id="corr_mvp2_returned",
    )
    await authority.mark_implemented(
        release_id,
        actor_id="actor_maker_mvp2",
        correlation_id="corr_mvp2_returned",
    )
    check = AssuranceEvaluator().evaluate(
        test_id="mvp2_positive",
        category=TestCategory.POSITIVE,
        expected=ExpectedBehavior(status="SUCCESS"),
        observed=ObservedBehavior(status="SUCCESS"),
    )
    await authority.record_automated_assurance(
        release_id,
        AutomatedAssuranceReport(
            checks=(check,), required_categories=frozenset({TestCategory.POSITIVE})
        ),
        actor_id="actor_checker_mvp2",
        correlation_id="corr_mvp2_returned",
    )
    await authority.record_ai_review_package(
        release_id,
        ReviewPackageReference(
            review_id=review_id,
            tenant_id="tenant_mvp2",
            workspace_id="workspace_mvp2",
            subject_id="agent.mvp2.returned",
            subject_version="1.0.0",
            contract_version="1.0.0",
            evidence_uri="urn:alos:evidence:mvp2-returned",
            recorded_at=datetime.now(UTC),
        ),
        actor_id="genesis_ai_review",
        correlation_id="corr_mvp2_returned",
    )
    assert authority.get(release_id).state is ReleaseState.AI_REVIEWED
    await authority.submit_for_it(
        release_id,
        actor_id="actor_checker_mvp2",
        correlation_id="corr_mvp2_returned",
    )
    returned = await authority.record_it_decision(
        release_id,
        AuthoritativeDecision(
            decision_id="decision_mvp2_returned",
            review_id=review_id,
            decision_type=AuthorityLevel.IT,
            outcome=DecisionOutcome.RETURNED,
            decided_by="actor_it_mvp2",
            rationale="Return the draft for correction.",
            decided_at=datetime.now(UTC),
        ),
        correlation_id="corr_mvp2_returned",
    )
    assert returned.state is ReleaseState.RETURNED
    with pytest.raises(ReleaseConflictError):
        await authority.release(
            release_id,
            actor_id="actor_release_mvp2",
            correlation_id="corr_mvp2_returned",
        )
