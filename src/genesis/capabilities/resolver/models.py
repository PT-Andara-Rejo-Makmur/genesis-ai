"""Typed, non-authoritative inputs and outputs for capability resolution."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.capabilities.models.definition import CapabilityType

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DataClassification = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    actor_id: str = Field(min_length=3, max_length=128)
    correlation_id: str = Field(min_length=3, max_length=128)
    statement: str = Field(min_length=20, max_length=10_000)
    scope_refs: tuple[str, ...] = Field(min_length=1)
    permission_refs: tuple[str, ...] = ()
    data_classification: DataClassification = "INTERNAL"
    preferred_capability_type: CapabilityType | None = None


class CapabilityCatalogItem(BaseModel):
    """Read-only catalog projection supplied by authoritative ALOS Backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str = Field(min_length=3, max_length=128)
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
    model_config = ConfigDict(extra="forbid", frozen=True)
    normalized_intent: str
    domains: tuple[str, ...]
    candidate_capability_ids: tuple[str, ...]
    recommended_type: CapabilityType
    risk_level: RiskLevel
    requires_agent: bool
    rationale: tuple[str, ...]


class CapabilityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    understanding: RequirementUnderstanding
    resolved: tuple[CapabilityCatalogItem, ...]
    missing_capability_ids: tuple[str, ...]
    required_tool_ids: tuple[str, ...]
    required_permission_refs: tuple[str, ...]
    activation_readiness: Literal["READY_FOR_DRAFT", "NEEDS_CONFIGURATION"]
