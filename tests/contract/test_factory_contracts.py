from pathlib import Path

from genesis.capabilities.resolver import Requirement
from genesis.contracts import CanonicalContractCatalog
from genesis.control_plane.factory import CapabilityFactory, FactoryAnalysisRequest

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def test_factory_output_validates_against_canonical_contracts() -> None:
    contracts = CanonicalContractCatalog(CONTRACTS_ROOT)
    result = CapabilityFactory(contracts=contracts).analyze(
        FactoryAnalysisRequest(
            requirement=Requirement(
                tenant_id="tenant_contract",
                organization_id="organization_contract",
                workspace_id="workspace_contract",
                actor_id="actor_contract",
                correlation_id="corr_contract_001",
                statement="Rancang agent untuk menganalisis dokumen perusahaan secara aman",
                scope_refs=("scope.workspace",),
            )
        )
    )

    contracts.validate(
        "https://schemas.alos.dev/v1/capability/capability-draft.schema.json",
        result.capability_draft,
    )
    assert result.agent_proposal is not None
    contracts.validate(
        "https://schemas.alos.dev/v1/agent/agent-definition.schema.json",
        result.agent_proposal.agent_definition,
    )
