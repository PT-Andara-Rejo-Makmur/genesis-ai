from pathlib import Path

from genesis.capabilities import CapabilityType
from genesis.capabilities.resolver import CapabilityCatalogItem
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def test_broad_actor_permissions_do_not_expand_create_proposal_permissions() -> None:
    catalog = (
        CapabilityCatalogItem(
            capability_id="document.read",
            version="1.0.0",
            name="Read approved document",
            purpose="Read one governed document through Backend",
            capability_type=CapabilityType.TOOL_REQUIREMENT,
            backing_tool_ids=("document.read",),
            permission_refs=("sources.read",),
            keywords=("document", "dokumen"),
        ),
    )

    result = CapabilityFactory(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT)
    ).analyze(
        FactoryAnalysisRequest.model_validate(
            {
                "requirement": {
                    "execution_context": {
                        "tenant_id": "tenant_regression",
                        "organization_id": "organization_regression",
                        "workspace_id": "workspace_regression",
                        "actor_id": "actor_regression",
                        "authority_context": {
                            "role": "REQUESTER",
                            "authority_level": "REQUESTER",
                        },
                        "correlation_id": "corr_least_privilege_001",
                        "scope_refs": ["scope.workspace"],
                        "permission_refs": [
                            "admin.all",
                            "registry.approve",
                            "release.execute",
                            "sources.read",
                        ],
                        "data_classification": "INTERNAL",
                    },
                    "statement": "Rancang agent untuk mencari dan membaca dokumen secara aman",
                },
                "capability_catalog": [item.model_dump(mode="json") for item in catalog],
            }
        )
    )

    assert result.resolution.decision == "CREATE"
    assert result.resolution.required_permission_refs == ("sources.read",)
    assert result.agent_draft is not None
    assert result.agent_draft.permission_refs == ("sources.read",)
    assert result.agent_draft.agent_definition["permission_refs"] == ["sources.read"]
    assert result.capability_draft is not None
    assert result.capability_draft["permission_refs"] == ["sources.read"]
    assert result.capability_draft["output_state"] == "DRAFT"
    assert "REGISTER_CAPABILITY_DRAFT" in result.handoff.requested_operations
    assert result.handoff.authoritative_state_changed is False
