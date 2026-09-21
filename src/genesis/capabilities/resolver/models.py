"""Typed, non-authoritative inputs and outputs for capability resolution."""

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from genesis.capabilities.models.definition import CapabilityType

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DataClassification = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
ResolutionDecision = Literal["REUSE", "CREATE"]


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    actor_id: str = Field(min_length=3, max_length=128)
    correlation_id: str = Field(min_length=3, max_length=128)
    requirement_id: str | None = Field(min_length=3, max_length=128, default=None)
    statement: str = Field(min_length=20, max_length=10_000)
    scope_refs: tuple[str, ...] = Field(min_length=1)
    permission_refs: tuple[str, ...] = ()
    data_classification: DataClassification = "INTERNAL"
    preferred_capability_type: CapabilityType | None = None


class CapabilityCatalogItem(BaseModel):
    """Read-only catalog projection supplied by authoritative ALOS Backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str = Field(min_length=3, max_length=128)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    capability_type: CapabilityType
    risk_level: RiskLevel = "LOW"
    availability: Literal["AVAILABLE", "UNAVAILABLE", "DEGRADED"] = "AVAILABLE"
    configuration_status: Literal["CONFIGURED", "NEEDS_CONFIGURATION", "NOT_APPLICABLE"] = (
        "CONFIGURED"
    )
    backing_tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


class RequirementUnderstanding(BaseModel):
    """Canonical, non-authoritative RequirementUnderstanding (contract v1).

    `ambiguity` is a typed signal that must always be present so the Backend can
    fail closed; the Backend — never the AI — decides what an ambiguity signal
    means for governance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement_id: str | None = None
    objective: str | None = None
    trigger: str | None = None
    capability_need: tuple[str, ...] = ()
    data_need: tuple[str, ...] = ()
    source_semantics: tuple[str, ...] = ()
    ambiguity: Literal["NONE", "NEEDS_CLARIFICATION"] = "NONE"
    normalized_intent: str
    domains: tuple[str, ...]
    candidate_capability_ids: tuple[str, ...]
    recommended_type: CapabilityType
    risk_level: RiskLevel
    requires_agent: bool
    rationale: tuple[str, ...]

    @model_serializer(mode="wrap")
    def _omit_undetermined(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Omit optional semantics the AI did not determine instead of emitting null.

        The frozen canonical schema types these fields as strings/arrays, so an
        explicit JSON null would be an invalid contract payload for both GENESIS
        and the ALOS Backend validator.
        """

        serialized = handler(self)
        return {key: value for key, value in serialized.items() if value is not None}


class CapabilityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    understanding: RequirementUnderstanding
    decision: ResolutionDecision
    reason: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    scope_refs: tuple[str, ...] = Field(min_length=1)
    resolved: tuple[CapabilityCatalogItem, ...]
    missing_capability_ids: tuple[str, ...]
    required_tool_ids: tuple[str, ...]
    required_permission_refs: tuple[str, ...]
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    test_requirements: tuple[str, ...] = Field(min_length=1)
    activation_readiness: Literal[
        "READY_FOR_REUSE", "READY_FOR_DRAFT", "NEEDS_CONFIGURATION"
    ]
    human_gate_required: bool = True
