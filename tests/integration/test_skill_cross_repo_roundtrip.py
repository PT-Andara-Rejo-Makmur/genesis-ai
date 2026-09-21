"""Reproducible server-side contract/Backend/GENESIS skill roundtrip."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

pytest.importorskip("sqlalchemy", reason="cross-repo harness requires Backend dependencies")

WORKSPACE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WORKSPACE / "alos-backend" / "src"))

from alos.agents.registry import AgentRegistry  # noqa: E402
from alos.audit import InMemoryAuditRepository  # noqa: E402
from alos.contracts import CanonicalContractCatalog as BackendCatalog  # noqa: E402
from alos.identity import Principal  # noqa: E402
from alos.skills.registry import SkillRegistry  # noqa: E402

from genesis.contracts import CanonicalContractCatalog  # noqa: E402
from genesis.research import (  # noqa: E402
    EvidenceCandidate,
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchChannel,
    ResearchDecisionKind,
    ResearchDecisionRequest,
    ResearchDomain,
    ResearchRisk,
)
from genesis.research.sources import FreshnessStatus, SourceReliability  # noqa: E402
from genesis.runtime.context import DataClassification  # noqa: E402
from genesis.skills.authorization import SkillAuthorizationSnapshot  # noqa: E402
from genesis.skills.loader import FileSystemSkillLoader, SkillReference  # noqa: E402
from genesis.skills.runtime import SkillRuntime, SkillRuntimeStatus  # noqa: E402

CONTRACTS_ROOT = WORKSPACE / "alos-contracts"
SKILLS_ROOT = WORKSPACE / "genesis-ai" / "blueprints" / "skills" / "research"
PACKAGES = {
    "technology": "skill.research.technology",
    "property_business": "skill.research.property_business",
    "management": "skill.research.management",
    "property_market": "skill.research.property_market",
}


def principal() -> Principal:
    return Principal(
        actor_id="actor_skill_reviewer",
        tenant_id="tenant_roundtrip",
        organization_id="organization_roundtrip",
        workspace_id="workspace_roundtrip",
        permissions=frozenset(),
        scopes=frozenset({"scope.research"}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("package", "skill_id"), PACKAGES.items())
async def test_manifest_registry_agent_authorization_and_runtime_roundtrip(
    package: str,
    skill_id: str,
) -> None:
    payload = yaml.safe_load((SKILLS_ROOT / package / "skill.yaml").read_text(encoding="utf-8"))
    contracts = BackendCatalog(CONTRACTS_ROOT)
    audit = InMemoryAuditRepository()
    skills = SkillRegistry(contracts, audit)
    agents = AgentRegistry(contracts, audit)
    actor = principal()
    draft = await skills.register(
        payload,
        tenant_id=actor.tenant_id,
        organization_id=actor.organization_id,
        workspace_id=actor.workspace_id,
        actor_id=actor.actor_id,
        correlation_id="corr_roundtrip_001",
    )
    approved = await skills.approve(
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
        subject_id=skill_id,
        version="1.0.0",
        actor_id=actor.actor_id,
        decision_id="decision_roundtrip_001",
        authority="IT",
        correlation_id="corr_roundtrip_001",
    )
    await skills.activate(
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
        subject_id=skill_id,
        version="1.0.0",
        actor_id=actor.actor_id,
        release_id="release_roundtrip_001",
        correlation_id="corr_roundtrip_001",
    )
    agent_payload = {
        "tenant_id": actor.tenant_id,
        "organization_id": actor.organization_id,
        "workspace_id": actor.workspace_id,
        "agent_id": f"agent.{package}",
        "agent_version": "1.0.0",
        "owner_actor_id": actor.actor_id,
        "name": f"Research {package}",
        "purpose": "Run governed research.",
        "risk_level": "MEDIUM",
        "capability_ids": ["capability_research"],
        "skill_refs": [{"skill_id": skill_id, "skill_version": "1.0.0"}],
        "model_policy_ref": "model-policy.research",
        "tool_ids": [],
        "permission_refs": [],
        "scope_refs": ["scope.research"],
        "delegation_policy": {"enabled": False, "max_depth": 0},
    }
    agent_draft = await agents.register(
        agent_payload,
        tenant_id=actor.tenant_id,
        organization_id=actor.organization_id,
        workspace_id=actor.workspace_id,
        actor_id=actor.actor_id,
        correlation_id="corr_roundtrip_001",
    )
    agent_approved = await agents.approve(
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
        subject_id=agent_draft.subject_id,
        version="1.0.0",
        actor_id=actor.actor_id,
        decision_id="decision_agent_roundtrip",
        authority="IT",
        correlation_id="corr_roundtrip_001",
    )
    await agents.activate(
        tenant_id=actor.tenant_id,
        workspace_id=actor.workspace_id,
        subject_id=agent_approved.subject_id,
        version="1.0.0",
        actor_id=actor.actor_id,
        release_id="release_agent_roundtrip",
        correlation_id="corr_roundtrip_001",
    )
    authorized = skills.get_authorized(principal=actor, subject_id=skill_id, version="1.0.0")
    reference = SkillReference(skill_id=authorized.subject_id, skill_version=authorized.version)
    snapshot = SkillAuthorizationSnapshot(
        tenant_id=actor.tenant_id,
        organization_id=actor.organization_id,
        workspace_id=actor.workspace_id,
        correlation_id="corr_roundtrip_001",
        authorized_skill_refs=(reference,),
        permission_refs=(),
        scope_refs=("scope.research",),
        allowed_tool_ids=(),
    )
    runtime = SkillRuntime(
        loader=FileSystemSkillLoader(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    )
    result = runtime.prepare(
        SKILLS_ROOT,
        authorization=snapshot,
        goal=str(payload["name"]),
        maximum_selected=1,
    )
    assert draft.state.value == "DRAFT"
    assert approved.state.value == "APPROVED"
    assert result.status is SkillRuntimeStatus.READY
    assert result.loaded_skills[0].specification.skill_id == skill_id
    assert result.loaded_skills[0].specification.skill_version == "1.0.0"
    assert result.loaded_skills[0].instructions.startswith("#")


def test_selected_research_skill_uses_internal_or_backend_external_boundary() -> None:
    common = {
        "correlation_id": "corr_research_roundtrip",
        "domain": ResearchDomain.TECHNOLOGY,
        "question": "Evaluate the authorized technology evidence.",
        "risk": ResearchRisk.MEDIUM,
        "data_classification": DataClassification.INTERNAL,
        "authorized_scope_refs": ["scope.research"],
        "authorized_permission_refs": ["research.external.read"],
        "allowed_tool_ids": ["research.external.retrieve"],
        "external": ExternalResearchBoundary(
            enabled=True,
            tool_id="research.external.retrieve",
            permission_ref="research.external.read",
            estimated_cost=1.0,
        ),
        "maximum_external_cost": 2.0,
    }
    evidence = EvidenceCandidate(
        evidence_id="evidence_roundtrip",
        channel=ResearchChannel.INTERNAL_SOURCE,
        freshness=FreshnessStatus.CURRENT,
        reliability=SourceReliability.HIGH,
        available=True,
        scope_refs=("scope.research",),
        data_classification=DataClassification.INTERNAL,
    )
    decider = ExternalResearchDecider(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    internal = decider.decide(ResearchDecisionRequest(**common, evidence=(evidence,)))
    external = decider.decide(ResearchDecisionRequest(**common, evidence=()))
    assert internal.decision is ResearchDecisionKind.USE_INTERNAL_SOURCE
    assert internal.correlation_id == "corr_research_roundtrip"
    assert external.decision is ResearchDecisionKind.REQUEST_EXTERNAL_RESEARCH
    assert external.retrieval is not None
    assert external.retrieval.boundary == "BACKEND_TOOL_EXECUTOR"
    assert external.external_content_trust == "UNTRUSTED"
