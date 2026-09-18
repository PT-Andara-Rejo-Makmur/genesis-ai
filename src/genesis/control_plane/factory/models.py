from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.capabilities import CapabilityDefinition
from genesis.capabilities.models.definition import CapabilityType
from genesis.capabilities.resolver import (
    CapabilityCatalogItem,
    CapabilityResolution,
    Requirement,
)
from genesis.evals import EvaluationPlan

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class DraftSpecification(BaseModel):
    """Non-authoritative proposal details missing from the current canonical draft schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    identifier: str = Field(min_length=3)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    lifecycle_state: Literal["DRAFT"] = "DRAFT"
    purpose: str = Field(min_length=1)
    capability_type: CapabilityType
    scope_refs: tuple[str, ...] = Field(min_length=1)
    tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = Field(min_length=1)
    risk_level: RiskLevel
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    test_requirements: tuple[str, ...] = Field(min_length=1)


class CapabilityFactoryProposal(BaseModel):
    """A proposal only; ALOS Backend owns registry activation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str = Field(min_length=3)
    requirement: str = Field(min_length=1)
    capability: CapabilityDefinition
    rationale: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class FactoryAnalysisRequest(BaseModel):
    """Backend-supplied requirement plus read-only authoritative catalog snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement: Requirement
    capability_catalog: tuple[CapabilityCatalogItem, ...] = ()


class StructuredAgentProposal(BaseModel):
    """A draft proposal only; it cannot approve or activate itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    draft_id: str
    status: Literal["DRAFT"] = "DRAFT"
    specification: DraftSpecification
    agent_definition: dict[str, Any]
    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    test_plan: EvaluationPlan


type RegistryOperation = Literal[
    "REGISTER_CAPABILITY_DRAFT", "REGISTER_AGENT_DRAFT", "START_GOVERNANCE"
]


class RegistryHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    target_service: Literal["alos-backend"] = "alos-backend"
    transport: Literal["typed_internal_api"] = "typed_internal_api"
    requested_operations: tuple[RegistryOperation, ...]
    authoritative_state_changed: Literal[False] = False


class FactoryAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    correlation_id: str
    resolution: CapabilityResolution
    existing_capability_refs: tuple[CapabilityCatalogItem, ...] = ()
    capability_draft: dict[str, Any] | None = None
    capability_specification: DraftSpecification | None = None
    agent_proposal: StructuredAgentProposal | None = None
    evidence_requirements: tuple[str, ...]
    missing_dependencies: tuple[str, ...]
    handoff: RegistryHandoff
