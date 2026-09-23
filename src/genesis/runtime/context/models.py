"""Typed, non-authoritative context models for bounded GENESIS execution."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.runtime.limits import ExecutionBudget


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ContextSource(StrEnum):
    SYSTEM = "SYSTEM"
    INTERNAL = "INTERNAL"
    MEMORY = "MEMORY"
    EXTERNAL = "EXTERNAL"


class ContextTrust(StrEnum):
    GOVERNED = "GOVERNED"
    UNTRUSTED = "UNTRUSTED"


class Freshness(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ContextPriority(IntEnum):
    SYSTEM_SECURITY_AUTHORITY = 1
    EXECUTION_CONTEXT_SCOPE = 2
    USER_GOAL = 3
    REQUIRED_BUSINESS_CONTEXT = 4
    AUTHORITATIVE_EVIDENCE = 5
    RELEVANT_MEMORY = 6
    EXTERNAL_CONTEXT = 7
    SUPPORTING_CONTEXT = 8


class AuthorityContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str = Field(min_length=1, max_length=128)
    role_refs: tuple[str, ...] = ()
    authority_level: Literal["REQUESTER", "OPERATOR", "IT_APPROVER", "DIRECTOR_APPROVER", "SYSTEM"]


class ExecutionContextView(BaseModel):
    """Typed view created only after canonical ExecutionContext validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    actor_id: str = Field(min_length=3, max_length=128)
    authority_context: AuthorityContext
    permission_refs: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)
    data_classification: DataClassification
    correlation_id: str = Field(min_length=3, max_length=128)
    execution_budget: ExecutionBudget


class BackendContextAuthorization(BaseModel):
    """Expected Backend-issued boundary; comparison grants no authority in GENESIS."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    actor_id: str = Field(min_length=3, max_length=128)
    allowed_role_refs: tuple[str, ...] = Field(min_length=1)
    allowed_authority_levels: tuple[
        Literal["REQUESTER", "OPERATOR", "IT_APPROVER", "DIRECTOR_APPROVER", "SYSTEM"], ...
    ] = Field(min_length=1)
    allowed_scope_refs: tuple[str, ...] = Field(min_length=1)
    allowed_permission_refs: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    allowed_classifications: tuple[DataClassification, ...] = Field(min_length=1)


class ContextScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    division_refs: tuple[str, ...] = ()
    project_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_business_scope(self) -> ContextScope:
        if not self.division_refs and not self.project_refs:
            raise ValueError("division_refs or project_refs is required")
        return self

    @property
    def all_refs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.division_refs, *self.project_refs)))


class EvidenceReference(BaseModel):
    """Typed projection of the canonical EvidenceRef used by ContextBundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    run_id: str = Field(min_length=3, max_length=128)
    correlation_id: str = Field(min_length=3, max_length=128)
    scope_refs: tuple[str, ...] = Field(min_length=1)
    evidence_id: str = Field(min_length=3, max_length=128)
    source_id: str = Field(min_length=3, max_length=128)
    uri: str = Field(min_length=1)
    captured_at: datetime
    retrieved_at: datetime
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    source_version: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    excerpt: str = ""
    data_classification: DataClassification
    source_type: Literal["INTERNAL", "EXTERNAL"]
    freshness: Literal["CURRENT", "STALE", "UNKNOWN"]
    reliability: Literal["UNVERIFIED", "LOW", "MEDIUM", "HIGH"]
    content_trust: Literal["GOVERNED", "UNTRUSTED"]
    instruction_authority: Literal[False] = False
    validation_status: Literal["PENDING", "VALID", "INVALID", "WAIVED"]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_external_source_semantics(self) -> EvidenceReference:
        if self.source_type == "EXTERNAL" and self.content_trust != "UNTRUSTED":
            raise ValueError("EXTERNAL evidence must be UNTRUSTED")
        return self


class ContextSegment(BaseModel):
    """Already-authorized candidate context; it cannot add scope, tools, or permission."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    segment_id: str = Field(min_length=3, max_length=128)
    key: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=200_000)
    priority: ContextPriority
    source: ContextSource
    trust: ContextTrust
    freshness: Freshness = Freshness.CURRENT
    data_classification: DataClassification
    scope_refs: tuple[str, ...] = Field(min_length=1)
    permission_refs: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    evidence: EvidenceReference | None = None
    lineage_evidence_refs: tuple[EvidenceReference, ...] = ()
    memory_ref: str | None = Field(default=None, min_length=3, max_length=128)

    @model_validator(mode="after")
    def enforce_source_semantics(self) -> ContextSegment:
        if self.source is ContextSource.EXTERNAL and self.trust is not ContextTrust.UNTRUSTED:
            raise ValueError("EXTERNAL context must be UNTRUSTED")
        if self.priority is ContextPriority.AUTHORITATIVE_EVIDENCE and self.evidence is None:
            raise ValueError("authoritative evidence requires EvidenceReference")
        if self.source is ContextSource.MEMORY and self.memory_ref is None:
            raise ValueError("MEMORY context requires memory_ref")
        if self.source is ContextSource.MEMORY and not self.lineage_evidence_refs:
            raise ValueError("MEMORY context requires evidence lineage")
        if self.source is not ContextSource.MEMORY and self.lineage_evidence_refs:
            raise ValueError("historical lineage is only valid for MEMORY context")
        return self

    @property
    def all_evidence(self) -> tuple[EvidenceReference, ...]:
        evidence = (self.evidence,) if self.evidence is not None else ()
        return tuple(
            {item.evidence_id: item for item in (*evidence, *self.lineage_evidence_refs)}.values()
        )

    @property
    def size_characters(self) -> int:
        return len(self.content)

    @property
    def required(self) -> bool:
        return self.priority <= ContextPriority.AUTHORITATIVE_EVIDENCE


class ContextSelectionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    maximum_characters: int = Field(ge=1)
    selected_characters: int = Field(ge=0)
    selected_segment_ids: tuple[str, ...]
    dropped_segment_ids: tuple[str, ...]
    reason_by_segment: dict[str, str]


class ContextSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    selected: tuple[ContextSegment, ...]
    dropped: tuple[ContextSegment, ...]
    metadata: ContextSelectionMetadata


class RuntimeContextBundle(BaseModel):
    """Runtime wrapper around a canonical ContextBundle projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    context_id: str = Field(min_length=3, max_length=128)
    goal: str = Field(min_length=1)
    actor_id: str
    tenant_id: str
    organization_id: str
    workspace_id: str
    authority_context: AuthorityContext
    scope: ContextScope
    capability_id: str = Field(min_length=3, max_length=128)
    allowed_tool_ids: tuple[str, ...]
    execution_budget: ExecutionBudget
    memory_refs: tuple[str, ...]
    evidence_refs: tuple[EvidenceReference, ...]
    correlation_id: str
    selected_segments: tuple[ContextSegment, ...]
    selection: ContextSelectionMetadata
    canonical_context_bundle: dict[str, Any]


class ContextFailure(Exception):
    """Structured fail-closed result preserving the Backend correlation id."""

    def __init__(
        self,
        code: str,
        message: str,
        correlation_id: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.correlation_id = correlation_id
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "retryable": False,
            "details": dict(self.details),
        }
