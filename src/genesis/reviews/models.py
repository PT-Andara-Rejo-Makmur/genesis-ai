from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewType(StrEnum):
    BUSINESS = "BUSINESS"
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"
    EVIDENCE = "EVIDENCE"
    COST_RISK = "COST_RISK"


class AIReviewStatus(StrEnum):
    READY = "READY"
    REVISION_RECOMMENDED = "REVISION_RECOMMENDED"
    BLOCKED_BY_EVIDENCE = "BLOCKED_BY_EVIDENCE"
    RISK_FOUND = "RISK_FOUND"


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    finding_id: str = Field(min_length=3)
    severity: str
    summary: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class AIReviewResult(BaseModel):
    """Recommendation-only result. No authoritative approval state exists."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    review_id: str = Field(min_length=3)
    review_type: ReviewType
    status: AIReviewStatus
    findings: tuple[ReviewFinding, ...] = ()
    recommendations: tuple[str, ...] = ()


class ReviewPackageDraft(BaseModel):
    """Draft mapped to the canonical ReviewPackage contract before transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_id: str
    results: tuple[AIReviewResult, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
