import pytest
from pydantic import ValidationError

from genesis.agents.definitions import AgentDefinition
from genesis.capabilities import CapabilityType


def test_capability_taxonomy_is_complete_and_not_agent_only() -> None:
    assert {item.value for item in CapabilityType} == {
        "AGENT",
        "SKILL",
        "WORKFLOW",
        "RULE",
        "VALIDATOR",
        "REPORT",
        "HUMAN_TASK",
        "SCHEDULE",
        "EVENT_HANDLER",
        "CONNECTOR_REQUIREMENT",
        "TOOL_REQUIREMENT",
        "COMPOSITE",
    }


def test_agent_definition_is_data_driven_and_validated() -> None:
    definition = AgentDefinition(
        agent_id="agent_research_001",
        agent_version="1.0.0",
        name="Research Analyst",
        purpose="Produce evidence-backed research findings.",
        capability_ids=("cap_research",),
        scope_refs=("scope.research",),
        model_policy_ref="model-policy.standard-v1",
    )
    assert definition.agent_id == "agent_research_001"


def test_agent_definition_rejects_invalid_version() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition(
            agent_id="agent_research_001",
            agent_version="latest",
            name="Research Analyst",
            purpose="Research",
            capability_ids=("cap_research",),
            scope_refs=("scope.research",),
            model_policy_ref="model-policy.standard-v1",
        )
