from pathlib import Path

from genesis.capabilities import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem, Requirement
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest
from genesis.evals import EvaluationTaxonomy

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def requirement(statement: str) -> Requirement:
    return Requirement(
        tenant_id="tenant_demo",
        organization_id="organization_demo",
        workspace_id="workspace_demo",
        actor_id="actor_demo",
        correlation_id="corr_factory_001",
        statement=statement,
        scope_refs=("scope.workspace",),
        permission_refs=("document.read",),
    )


def factory() -> CapabilityFactory:
    return CapabilityFactory(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def test_capability_first_does_not_force_report_into_agent() -> None:
    result = factory().analyze(
        FactoryAnalysisRequest(
            requirement=requirement(
                "Buat laporan ringkas mengenai status operasional perusahaan saat ini"
            )
        )
    )

    assert result.resolution.understanding.recommended_type is CapabilityType.REPORT
    assert result.agent_proposal is None
    assert result.capability_draft["output_state"] == "DRAFT"
    assert result.handoff.requested_operations == ("REGISTER_CAPABILITY_DRAFT",)
    assert result.handoff.authoritative_state_changed is False


def test_agent_factory_produces_canonical_draft_and_real_negative_expectation() -> None:
    catalog = (
        CapabilityCatalogItem(
            capability_id="document.read",
            name="Read approved document",
            purpose="Read one versioned source through Backend",
            capability_type=CapabilityType.TOOL_REQUIREMENT,
            backing_tool_ids=("document.read",),
            permission_refs=("document.read",),
            keywords=("document", "dokumen"),
        ),
    )
    result = factory().analyze(
        FactoryAnalysisRequest(
            requirement=requirement(
                "Rancang agent untuk menganalisis dokumen dan menyajikan bukti terikat sumber"
            ),
            capability_catalog=catalog,
        )
    )

    assert result.agent_proposal is not None
    proposal = result.agent_proposal
    assert proposal.status == "DRAFT"
    assert proposal.agent_definition["output_state"] == "DRAFT"
    assert "No direct database access." in proposal.agent_definition["restrictions"]
    assert proposal.prompt_version == "1.0.0"
    negative = next(
        case for case in proposal.test_plan.cases if case.taxonomy is EvaluationTaxonomy.NEGATIVE
    )
    assert negative.expected_status == "DENIED"
    assert negative.expected_error_code == "AUTHORIZATION_DENIED"
    assert result.handoff.target_service == "alos-backend"


def test_missing_capabilities_are_explicit_dependencies() -> None:
    result = factory().analyze(
        FactoryAnalysisRequest(
            requirement=requirement(
                "Rancang agent untuk mencari dokumen dan membandingkan konflik kontrak"
            )
        )
    )

    assert "document.read" in result.missing_dependencies
    assert result.resolution.activation_readiness == "NEEDS_CONFIGURATION"
