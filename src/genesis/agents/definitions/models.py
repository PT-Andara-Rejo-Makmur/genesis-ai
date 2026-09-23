from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from genesis.contracts import CanonicalContractCatalog

SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"
AGENT_DEFINITION_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-definition.schema.json"


class AgentBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    blueprint_id: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1)
    purpose_template: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    default_skill_ids: tuple[str, ...] = ()


class AgentDefinition(BaseModel):
    """Typed runtime projection of the canonical AgentDefinition vocabulary."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: str = Field(min_length=3, max_length=128)
    agent_version: str = Field(pattern=SEMVER_PATTERN)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    skill_refs: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)
    approval_required: bool = False
    model_policy_ref: str = Field(min_length=1)
    delegation_policy: dict[str, Any] | None = None
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})

    @classmethod
    def from_canonical_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        contracts: "CanonicalContractCatalog",
    ) -> Self:
        """Validate the full canonical payload before creating the runtime projection."""

        canonical = contracts.validate(AGENT_DEFINITION_SCHEMA, payload)
        projection = {
            field_name: canonical[field_name]
            for field_name in cls.model_fields
            if field_name in canonical
        }
        return cls.model_validate(projection)
