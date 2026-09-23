from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.capabilities.models.definition import CapabilityType
from genesis.capabilities.resolver import (
    CapabilityCatalogItem,
    CapabilityResolution,
    Requirement,
)

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DataClassification = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]


class AuthorityContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str = Field(min_length=1)
    role_refs: tuple[str, ...] = ()
    authority_level: (
        Literal["REQUESTER", "OPERATOR", "IT_APPROVER", "DIRECTOR_APPROVER", "SYSTEM"] | None
    ) = None


class FactoryExecutionContext(BaseModel):
    """Canonical Backend-owned ExecutionContext projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    actor_id: str = Field(min_length=3, max_length=128)
    authority_context: AuthorityContext
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)
    data_classification: DataClassification
    correlation_id: str = Field(min_length=3, max_length=128)
    execution_budget: dict[str, Any] | None = None


class FactoryRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    execution_context: FactoryExecutionContext
    requirement_id: str | None = Field(min_length=3, max_length=128, default=None)
    statement: str = Field(min_length=20, max_length=10_000)
    preferred_capability_type: CapabilityType | None = None

    def to_resolver_requirement(self) -> Requirement:
        context = self.execution_context
        return Requirement(
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            correlation_id=context.correlation_id,
            requirement_id=self.requirement_id,
            statement=self.statement,
            scope_refs=context.scope_refs,
            permission_refs=context.permission_refs,
            data_classification=context.data_classification,
            preferred_capability_type=self.preferred_capability_type,
        )


class FactoryAnalysisRequest(BaseModel):
    """Backend-supplied requirement plus read-only authoritative catalog snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement: FactoryRequirement
    capability_catalog: tuple[CapabilityCatalogItem, ...] = ()


class AgentDraftProposal(BaseModel):
    """Canonical non-authoritative Agent draft projection for Backend governance."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    draft_id: str = Field(min_length=3)
    tenant_id: str = Field(min_length=3)
    organization_id: str = Field(min_length=3)
    workspace_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    agent_id: str = Field(min_length=3)
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    purpose: str = Field(min_length=1)
    capability_type: Literal[CapabilityType.AGENT] = CapabilityType.AGENT
    scope_refs: tuple[str, ...] = Field(min_length=1)
    tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = Field(min_length=1)
    risk_level: RiskLevel
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    test_requirements: tuple[str, ...] = Field(min_length=1)
    lifecycle_state: Literal["DRAFT"] = "DRAFT"
    agent_definition: dict[str, Any]


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
    agent_draft: AgentDraftProposal | None = None
    missing_dependencies: tuple[str, ...]
    handoff: RegistryHandoff
