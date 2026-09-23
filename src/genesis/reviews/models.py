from enum import StrEnum
from typing import Any, Literal

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
    PASS = "PASS"  # noqa: S105 - assurance status
    PASS_WITH_FINDINGS = "PASS_WITH_FINDINGS"  # noqa: S105
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


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
    summary: str = "Advisory AI review result."
    findings: tuple[ReviewFinding, ...] = ()
    recommendations: tuple[str, ...] = ()
    evidence_refs: tuple[dict[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()
    correlation_id: str | None = None
    completed_at: str | None = None


class ReviewPackageDraft(BaseModel):
    """Draft mapped to the canonical ReviewPackage contract before transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_id: str
    results: tuple[AIReviewResult, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()


class ReviewSubjectSnapshot(BaseModel):
    """Exact Backend/caller projection; no registry or mutable latest lookup occurs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    review_id: str = Field(min_length=3, max_length=128)
    subject_id: str = Field(min_length=3, max_length=128)
    subject_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    )
    tenant_id: str
    organization_id: str | None = None
    workspace_id: str
    correlation_id: str
    purpose: str = Field(min_length=1)
    materiality: Literal["NON_MATERIAL", "MATERIAL"]
    business_context: dict[str, Any] = Field(min_length=1)
    capability: dict[str, Any]
    scope: tuple[str, ...] = Field(min_length=1)
    permissions: tuple[str, ...] = ()
    skills: tuple[dict[str, Any], ...] = ()
    tools: tuple[dict[str, Any], ...] = ()
    model_policy: dict[str, Any]
    delegation_policy: dict[str, Any]
    execution_budget: dict[str, Any] = Field(min_length=1)
    evidence_refs: tuple[dict[str, Any], ...] = ()
