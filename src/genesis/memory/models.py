"""Immutable runtime projections for governed historical memory.

These models are deliberately internal to GENESIS. They are not storage or
cross-repository contracts and grant no authority.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.research.models import FindingKind, ResearchDomain
from genesis.runtime.context.models import (
    DataClassification,
    EvidenceReference,
    ExecutionContextView,
    Freshness,
)


class MemoryRecordStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
    INACTIVE = "INACTIVE"


class MemoryCandidate(BaseModel):
    """Backend-authorized candidate revalidated before it enters context."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    memory_id: str = Field(min_length=3, max_length=128)
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str = Field(min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    content: str = Field(min_length=1, max_length=200_000)
    scope_refs: tuple[str, ...] = Field(min_length=1)
    data_classification: DataClassification
    created_at: datetime
    expires_at: datetime | None = None
    freshness: Freshness = Freshness.CURRENT
    status: MemoryRecordStatus = MemoryRecordStatus.ACTIVE
    evidence_refs: tuple[EvidenceReference, ...] = ()
    source_refs: tuple[str, ...] = ()
    originating_run_id: str | None = Field(default=None, min_length=3, max_length=128)
    originating_correlation_id: str | None = Field(
        default=None, min_length=3, max_length=128
    )
    domain: ResearchDomain | None = None
    finding_kind: FindingKind | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_lineage_requirements(self) -> MemoryCandidate:
        if bool(self.originating_run_id) != bool(self.originating_correlation_id):
            raise ValueError("originating run and correlation must be supplied together")
        return self


class MemoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    goal: str = Field(min_length=1, max_length=20_000)
    requested_domains: tuple[ResearchDomain, ...] = ()
    requested_memory_refs: tuple[str, ...] = ()
    requested_source_refs: tuple[str, ...] = ()
    capability_context: tuple[str, ...] = ()
    allow_multi_domain: bool = False
    require_research_findings: bool = False
    maximum_candidates: int = Field(default=100, ge=1, le=1_000)
    maximum_selected: int = Field(default=6, ge=1, le=100)
    minimum_score: int = Field(default=1, ge=0)


class MemoryScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    total: int = Field(ge=0)
    lexical_overlap: int = Field(ge=0)
    domain_match: int = Field(ge=0)
    explicit_reference: int = Field(ge=0)
    source_match: int = Field(ge=0)
    evidence_strength: int = Field(ge=0)
    recency: int = Field(ge=0)
    rule_ids: tuple[str, ...]


class SelectedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate: MemoryCandidate
    score: MemoryScore
    fingerprint: str
    reason_code: str = "MEMORY_SELECTED"


class ExcludedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    memory_id: str
    reason_code: str


class SuppressedDuplicate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    memory_id: str
    selected_memory_id: str
    fingerprint: str
    reason_code: str = "DUPLICATE_SUPPRESSED"


class MemorySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    selected: tuple[SelectedMemory, ...]
    excluded: tuple[ExcludedMemory, ...]
    suppressed_duplicates: tuple[SuppressedDuplicate, ...]
    processed_candidates: int = Field(ge=0)


class MemoryWriteDisposition(StrEnum):
    PROPOSE = "PROPOSE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT = "REJECT"


class MemoryWriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str
    output_state: str = Field(min_length=1, max_length=64)
    execution_context: ExecutionContextView
    scope_refs: tuple[str, ...] = Field(min_length=1)
    data_classification: DataClassification
    evidence_refs: tuple[EvidenceReference, ...] = ()
    originating_run_id: str = Field(min_length=3, max_length=128)
    originating_correlation_id: str = Field(min_length=3, max_length=128)
    reusable: bool = False
    domain: ResearchDomain | None = None
    finding_kind: FindingKind | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryWriteProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str
    tenant_id: str
    organization_id: str
    workspace_id: str
    scope_refs: tuple[str, ...]
    data_classification: DataClassification
    evidence_refs: tuple[EvidenceReference, ...]
    originating_run_id: str
    originating_correlation_id: str
    domain: ResearchDomain | None = None
    finding_kind: FindingKind | None = None


class MemoryWriteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    disposition: MemoryWriteDisposition
    reason_codes: tuple[str, ...]
    proposal: MemoryWriteProposal | None = None
