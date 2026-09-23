from pathlib import Path

import pytest
from pydantic import ValidationError

from genesis.capabilities import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem, CapabilityResolver, Requirement
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest

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


def factory_request(
    statement: str,
    capability_catalog: tuple[CapabilityCatalogItem, ...] = (),
) -> FactoryAnalysisRequest:
    return FactoryAnalysisRequest.model_validate(
        {
            "requirement": {
                "execution_context": {
                    "tenant_id": "tenant_demo",
                    "organization_id": "organization_demo",
                    "workspace_id": "workspace_demo",
                    "actor_id": "actor_demo",
                    "authority_context": {
                        "role": "REQUESTER",
                        "authority_level": "REQUESTER",
                    },
                    "permission_refs": ["document.read"],
                    "scope_refs": ["scope.workspace"],
                    "data_classification": "INTERNAL",
                    "correlation_id": "corr_factory_001",
                },
                "statement": statement,
            },
            "capability_catalog": [item.model_dump(mode="json") for item in capability_catalog],
        }
    )


def test_capability_first_does_not_force_report_into_agent() -> None:
    result = factory().analyze(
        factory_request("Buat laporan ringkas mengenai status operasional perusahaan saat ini")
    )

    assert result.resolution.understanding.recommended_type is CapabilityType.REPORT
    assert result.resolution.decision == "CREATE"
    assert result.existing_capability_refs == ()
    assert result.agent_draft is None
    assert result.capability_draft is not None
    assert result.capability_draft["output_state"] == "DRAFT"
    assert result.capability_draft["lifecycle_state"] == "DRAFT"
    assert result.capability_draft["capability_type"] == "REPORT"
    assert result.capability_draft["scope_refs"] == ["scope.workspace"]
    assert result.capability_draft["risk_level"] == "MEDIUM"
    assert result.capability_draft["evidence_requirements"]
    assert result.capability_draft["test_requirements"]
    assert result.handoff.requested_operations == ("REGISTER_CAPABILITY_DRAFT",)
    assert result.handoff.authoritative_state_changed is False


def test_agent_factory_produces_canonical_draft_and_real_negative_expectation() -> None:
    catalog = (
        CapabilityCatalogItem(
            capability_id="document.read",
            version="1.0.0",
            name="Read approved document",
            purpose="Read one versioned source through Backend",
            capability_type=CapabilityType.TOOL_REQUIREMENT,
            backing_tool_ids=("document.read",),
            permission_refs=("document.read",),
            keywords=("document", "dokumen"),
        ),
    )
    result = factory().analyze(
        factory_request(
            "Rancang agent untuk menganalisis dokumen dan menyajikan bukti terikat sumber",
            catalog,
        )
    )

    assert result.agent_draft is not None
    proposal = result.agent_draft
    assert proposal.lifecycle_state == "DRAFT"
    assert proposal.version == "0.1.0"
    assert proposal.scope_refs == ("scope.workspace",)
    assert proposal.permission_refs == ("document.read",)
    assert "Approve or release its own proposal." in proposal.prohibited_actions
    assert proposal.agent_definition["output_state"] == "DRAFT"
    assert "No direct database access." in proposal.agent_definition["restrictions"]
    assert any("Negative test" in item for item in proposal.test_requirements)
    assert result.handoff.target_service == "alos-backend"


def test_missing_capabilities_are_explicit_dependencies() -> None:
    result = factory().analyze(
        factory_request("Rancang agent untuk mencari dokumen dan membandingkan konflik kontrak")
    )

    assert "document.read" in result.missing_dependencies
    assert result.resolution.decision == "CREATE"
    assert result.resolution.activation_readiness == "NEEDS_CONFIGURATION"


def test_resolver_reuses_complete_authoritative_catalog_match() -> None:
    result = CapabilityResolver().resolve(
        requirement("Buat laporan ringkas status operasional perusahaan untuk direview"),
        (
            CapabilityCatalogItem(
                capability_id="report.generate",
                version="1.0.0",
                name="Generate report",
                purpose="Create a reviewable report draft",
                capability_type=CapabilityType.REPORT,
                permission_refs=("report.read",),
            ),
        ),
    )

    assert result.decision == "REUSE"
    assert result.missing_capability_ids == ()
    assert result.required_permission_refs == ("report.read",)
    assert result.scope_refs == ("scope.workspace",)
    assert result.activation_readiness == "READY_FOR_REUSE"
    assert "report.generate" in result.reason


def test_factory_reuse_returns_backend_reference_without_draft_or_registry_create() -> None:
    catalog_item = CapabilityCatalogItem(
        capability_id="report.generate",
        version="1.0.0",
        name="Generate report",
        purpose="Create a reviewable report draft",
        capability_type=CapabilityType.REPORT,
        permission_refs=("report.read",),
    )

    result = factory().analyze(
        factory_request(
            "Buat laporan ringkas status operasional perusahaan untuk direview",
            (catalog_item,),
        )
    )

    assert result.resolution.decision == "REUSE"
    assert result.existing_capability_refs == (catalog_item,)
    assert result.capability_draft is None
    assert result.agent_draft is None
    assert result.handoff.requested_operations == ()
    assert result.handoff.authoritative_state_changed is False


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("Buat skill ringkas untuk merangkum informasi operasional internal", CapabilityType.SKILL),
        ("Buat workflow proses eskalasi temuan untuk tim operasional", CapabilityType.WORKFLOW),
        ("Buat aturan kebijakan retensi dokumen internal perusahaan", CapabilityType.RULE),
        ("Buat validator untuk validasi format laporan operasional", CapabilityType.VALIDATOR),
        ("Buat laporan status proyek untuk review manajemen perusahaan", CapabilityType.REPORT),
        ("Buat human task untuk manual review temuan berisiko tinggi", CapabilityType.HUMAN_TASK),
        ("Buat agent untuk koordinasi analisis lintas dokumen perusahaan", CapabilityType.AGENT),
    ],
)
def test_resolver_selects_simplest_supported_capability_type(
    statement: str, expected: CapabilityType
) -> None:
    assert CapabilityResolver().understand(requirement(statement)).recommended_type is expected


def test_invalid_requirement_context_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Requirement(
            tenant_id="tenant_demo",
            organization_id="organization_demo",
            workspace_id="workspace_demo",
            actor_id="actor_demo",
            correlation_id="corr_factory_001",
            statement="Requirement valid length tetapi scope authoritative tidak tersedia",
            scope_refs=(),
        )
