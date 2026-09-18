from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"


class AgentBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    blueprint_id: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1)
    purpose_template: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    default_skill_ids: tuple[str, ...] = ()


class AgentDefinition(BaseModel):
    """Data-driven definition consumed by a generic runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: str = Field(min_length=3, max_length=128)
    agent_version: str = Field(pattern=SEMVER_PATTERN)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    skill_ids: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)
    model_policy_ref: str = Field(min_length=1)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})


class AgentDraft(BaseModel):
    """A proposed definition. GENESIS cannot activate it by itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    draft_id: str = Field(min_length=3, max_length=128)
    definition: AgentDefinition
    created_by_run_id: str = Field(min_length=3, max_length=128)
    status: Literal["DRAFT", "SUBMITTED_FOR_REVIEW"] = "DRAFT"
