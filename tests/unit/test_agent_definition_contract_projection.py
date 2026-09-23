from pathlib import Path
from typing import Any

import pytest

from genesis.agents.definitions import AgentDefinition, AgentSkillRef
from genesis.contracts import CanonicalContractCatalog, ContractValidationError

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def canonical_agent_definition(skill_refs: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "agent_id": "agent.contract-projection",
        "agent_version": "1.0.0",
        "name": "Contract Projection Agent",
        "purpose": "Verify exact canonical skill references.",
        "capability_ids": ["capability.contract-projection"],
        "skill_refs": skill_refs,
        "model_policy_ref": "model-policy.standard-v1",
        "scope_refs": ["scope.contract-projection"],
        "delegation_policy": {"enabled": False, "max_depth": 0},
    }


def project(skill_refs: list[dict[str, str]]) -> AgentDefinition:
    return AgentDefinition.from_canonical_payload(
        canonical_agent_definition(skill_refs),
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
    )


def test_projects_one_exact_canonical_skill_ref() -> None:
    definition = project([{"skill_id": "skill.research.market", "skill_version": "1.2.3"}])

    assert definition.skill_refs == (
        AgentSkillRef(skill_id="skill.research.market", skill_version="1.2.3"),
    )


def test_projects_multiple_skill_refs_in_canonical_order_without_resolution() -> None:
    definition = project(
        [
            {"skill_id": "skill.research.market", "skill_version": "1.2.3"},
            {"skill_id": "skill.research.technology", "skill_version": "2.0.0-beta.1"},
        ]
    )

    assert tuple((item.skill_id, item.skill_version) for item in definition.skill_refs) == (
        ("skill.research.market", "1.2.3"),
        ("skill.research.technology", "2.0.0-beta.1"),
    )


def test_canonical_validation_rejects_skill_ref_without_version() -> None:
    payload = canonical_agent_definition([{"skill_id": "skill.research.market"}])

    with pytest.raises(ContractValidationError, match="skill_version"):
        AgentDefinition.from_canonical_payload(
            payload,
            contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        )


def test_canonical_validation_rejects_extra_skill_ref_property() -> None:
    payload = canonical_agent_definition(
        [
            {
                "skill_id": "skill.research.market",
                "skill_version": "1.2.3",
                "resolution": "latest",
            }
        ]
    )

    with pytest.raises(ContractValidationError, match="Additional properties"):
        AgentDefinition.from_canonical_payload(
            payload,
            contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        )


def test_projection_does_not_invent_or_replace_skill_authority() -> None:
    supplied = [{"skill_id": "skill.research.market", "skill_version": "3.4.5+build.7"}]

    definition = project(supplied)

    assert [item.model_dump(mode="json") for item in definition.skill_refs] == supplied
