from pathlib import Path

from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def test_factory_output_validates_against_canonical_contracts() -> None:
    contracts = CanonicalContractCatalog(CONTRACTS_ROOT)
    result = CapabilityFactory(contracts=contracts).analyze(
        FactoryAnalysisRequest(
            requirement={
                "execution_context": {
                    "tenant_id": "tenant_contract",
                    "organization_id": "organization_contract",
                    "workspace_id": "workspace_contract",
                    "actor_id": "actor_contract",
                    "authority_context": {
                        "role": "REQUESTER",
                        "authority_level": "REQUESTER",
                    },
                    "scope_refs": ["scope.workspace"],
                    "data_classification": "INTERNAL",
                    "correlation_id": "corr_contract_001",
                },
                "statement": "Rancang agent untuk menganalisis dokumen perusahaan secara aman",
            }
        )
    )

    contracts.validate(
        "https://schemas.alos.dev/v1/capability/capability-draft.schema.json",
        result.capability_draft,
    )
    assert result.agent_draft is not None
    contracts.validate(
        "https://schemas.alos.dev/v1/agent/agent-draft.schema.json",
        result.agent_draft.model_dump(mode="json"),
    )
    contracts.validate(
        "https://schemas.alos.dev/v1/factory/factory-analysis-result.schema.json",
        result.model_dump(mode="json"),
    )
