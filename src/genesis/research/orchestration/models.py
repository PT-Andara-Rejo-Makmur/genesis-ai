"""Immutable, non-canonical H7 research intelligence projections."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.research.models import ResearchDomain
from genesis.research.sources import (
    ContentTrust,
    FreshnessStatus,
    SourceReliability,
    SourceType,
)
from genesis.research.tool_selection import ResearchToolCategory
from genesis.runtime.context import DataClassification


class EvidenceNeed(StrEnum):
    CURRENT_STATE = "CURRENT_STATE"
    COMPARABLE = "COMPARABLE"
    RISK = "RISK"
    COST = "COST"
    GOVERNANCE = "GOVERNANCE"
    HISTORICAL = "HISTORICAL"


class EvidenceUsability(StrEnum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    WEAK = "WEAK"
    EXCLUDED = "EXCLUDED"


class QualityTier(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    EXCLUDED = "EXCLUDED"


class RetrievalStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    DENIED = "DENIED"
    NO_RESULT = "NO_RESULT"


class ClaimKind(StrEnum):
    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"
    GAP = "GAP"


class ConflictType(StrEnum):
    CLAIM_CONTRADICTION = "CLAIM_CONTRADICTION"
    SOURCE_VERSION = "SOURCE_VERSION"
    CURRENT_VS_STALE = "CURRENT_VS_STALE"


class SourceMode(StrEnum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    EXTERNAL_ONLY = "EXTERNAL_ONLY"
    MIXED = "MIXED"
    NONE = "NONE"


class ResearchSubquery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subquery_id: str = Field(min_length=3, max_length=128)
    question: str = Field(min_length=1, max_length=2_000)
    domain: ResearchDomain
    evidence_need: EvidenceNeed
    preferred_source_categories: tuple[ResearchToolCategory, ...] = Field(min_length=1)
    required_scope_refs: tuple[str, ...] = Field(min_length=1)
    materiality: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    reason_code: str = Field(min_length=3, max_length=128)


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    research_id: str = Field(min_length=3, max_length=128)
    domain: ResearchDomain
    original_question: str = Field(min_length=1)
    subqueries: tuple[ResearchSubquery, ...] = Field(min_length=1, max_length=8)
    max_subqueries: int = Field(ge=1, le=8)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def enforce_bounded_unique_subqueries(self) -> ResearchPlan:
        if len(self.subqueries) > self.max_subqueries:
            raise ValueError("Research plan exceeds max_subqueries")
        ids = [item.subquery_id for item in self.subqueries]
        if len(ids) != len(set(ids)):
            raise ValueError("Research subquery IDs must be unique")
        if any(item.domain is not self.domain for item in self.subqueries):
            raise ValueError("Research subquery domain must match plan domain")
        return self


class ResearchEvidenceItem(BaseModel):
    """Bounded evidence data; it never carries instruction authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_ref: dict[str, Any]
    content: str = Field(min_length=1, max_length=4_000)
    category: ResearchToolCategory
    subquery_ids: tuple[str, ...] = ()
    memory_ref: str | None = Field(default=None, min_length=3)
    child_task_id: str | None = Field(default=None, min_length=3)
    instruction_authority: Literal[False] = False

    @property
    def evidence_id(self) -> str:
        return str(self.evidence_ref.get("evidence_id", ""))

    @property
    def source_id(self) -> str:
        return str(self.evidence_ref.get("source_id", ""))

    @model_validator(mode="after")
    def enforce_external_data_semantics(self) -> ResearchEvidenceItem:
        source_type = self.evidence_ref.get("source_type")
        if source_type == SourceType.EXTERNAL.value and (
            self.evidence_ref.get("content_trust") != ContentTrust.UNTRUSTED.value
            or self.evidence_ref.get("instruction_authority") is not False
        ):
            raise ValueError("External research evidence must remain untrusted data")
        return self


class EvidenceQualityAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str
    tier: QualityTier
    freshness: FreshnessStatus
    reliability: SourceReliability
    usability: EvidenceUsability
    reason_codes: tuple[str, ...] = Field(min_length=1)
    confidence_cap: float = Field(ge=0, le=1)


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_id: str = Field(min_length=3, max_length=128)
    normalized_topic: str = Field(min_length=1, max_length=256)
    statement: str = Field(min_length=1, max_length=4_000)
    kind: ClaimKind
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def facts_require_evidence(self) -> ClaimDraft:
        if self.kind is ClaimKind.FACT and not self.evidence_ids:
            raise ValueError("FACT claim requires evidence")
        if self.kind is ClaimKind.GAP and self.evidence_ids:
            raise ValueError("GAP claim cannot fabricate evidence")
        return self


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_id: str
    normalized_topic: str
    statement: str
    kind: ClaimKind
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    confidence: float = Field(ge=0, le=1)
    limitations: tuple[str, ...] = ()


class DuplicateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim_ids: tuple[str, ...] = Field(min_length=2)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    reason_code: Literal["SAME_CLAIM_SAME_LINEAGE"] = "SAME_CLAIM_SAME_LINEAGE"


class CorroborationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    topic: str
    claim_ids: tuple[str, ...] = Field(min_length=2)
    source_ids: tuple[str, ...] = Field(min_length=2)
    evidence_ids: tuple[str, ...] = Field(min_length=2)


class ConflictAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    conflict_id: str
    topic: str
    competing_claim_ids: tuple[str, ...] = Field(min_length=2)
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    conflict_type: ConflictType
    unresolved: Literal[True] = True
    limitations: tuple[str, ...] = Field(min_length=1)


class ResearchFindingAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    finding_id: str
    domain: ResearchDomain
    statement: str
    fact_claim_ids: tuple[str, ...] = Field(min_length=1)
    conflict_ids: tuple[str, ...] = ()
    assumption_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    quality_reasons: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
    output_state: Literal["AI_INFERRED"] = "AI_INFERRED"


class ResearchRecommendationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recommendation_id: str
    finding_ids: tuple[str, ...] = Field(min_length=1)
    fact_claim_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...] = ()
    assumption_ids: tuple[str, ...] = ()
    proposed_action: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...] = Field(min_length=1)
    requires_human_review: Literal[True] = True
    backlog_candidate: Literal[True] = True


class RetrievalAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subquery_id: str
    tool_id: str | None = None
    category: ResearchToolCategory | None = None
    status: RetrievalStatus
    evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = Field(min_length=1)


class DelegatedResearchInput(BaseModel):
    """Validated H6 child data projection; it never becomes instruction authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    child_task_id: str = Field(min_length=3)
    status: Literal["COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"]
    validation_status: Literal["VALID", "INVALID"]
    evidence_items: tuple[ResearchEvidenceItem, ...] = ()
    instruction_authority: Literal[False] = False


class ModelCallUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    route_ids: tuple[str, ...] = ()

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: ModelCallUsage) -> ModelCallUsage:
        return ModelCallUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            estimated_cost=self.estimated_cost + other.estimated_cost,
            route_ids=(*self.route_ids, *other.route_ids),
        )


class ResearchOrchestrationResult(BaseModel):
    """Rich H7 analysis. This is not a canonical Backend contract or authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    plan: ResearchPlan
    source_mode: SourceMode
    retrieval_attempts: tuple[RetrievalAttempt, ...]
    evidence_items: tuple[ResearchEvidenceItem, ...]
    evidence_assessments: tuple[EvidenceQualityAssessment, ...]
    claims: tuple[ClaimAssessment, ...]
    duplicates: tuple[DuplicateAssessment, ...]
    corroborations: tuple[CorroborationAssessment, ...]
    conflicts: tuple[ConflictAssessment, ...]
    assumptions: tuple[ClaimAssessment, ...]
    gaps: tuple[ClaimAssessment, ...]
    findings: tuple[ResearchFindingAnalysis, ...]
    recommendations: tuple[ResearchRecommendationAnalysis, ...]
    canonical_result: dict[str, Any]
    limitations: tuple[str, ...]
    usage: ModelCallUsage
    requires_human_review: Literal[True] = True


class ResearchOrchestrationFailure(Exception):
    def __init__(self, code: str, message: str, correlation_id: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.correlation_id = correlation_id


CLASSIFICATION_RANK = {
    DataClassification.PUBLIC.value: 0,
    DataClassification.INTERNAL.value: 1,
    DataClassification.CONFIDENTIAL.value: 2,
    DataClassification.RESTRICTED.value: 3,
}
