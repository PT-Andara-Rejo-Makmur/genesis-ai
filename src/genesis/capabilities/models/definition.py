from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CapabilityType(StrEnum):
    AGENT = "AGENT"
    SKILL = "SKILL"
    WORKFLOW = "WORKFLOW"
    RULE = "RULE"
    VALIDATOR = "VALIDATOR"
    REPORT = "REPORT"
    HUMAN_TASK = "HUMAN_TASK"
    SCHEDULE = "SCHEDULE"
    EVENT_HANDLER = "EVENT_HANDLER"
    CONNECTOR_REQUIREMENT = "CONNECTOR_REQUIREMENT"
    TOOL_REQUIREMENT = "TOOL_REQUIREMENT"
    COMPOSITE = "COMPOSITE"


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1)
    capability_type: CapabilityType
    dependency_ids: tuple[str, ...] = ()
    requires_human_authority: bool = False
