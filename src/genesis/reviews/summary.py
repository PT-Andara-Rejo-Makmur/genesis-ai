"""Deterministic operational risk/evidence summary for human review."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from genesis.evals import (
    AIReadinessAssessment,
    AIReadinessStatus,
    EvaluationArea,
    EvaluationOutcome,
    EvaluationSeverity,
    EvaluationSuiteResult,
)


class RiskSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CompletionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    total_evals: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    not_run: int = Field(ge=0)
    required_complete: bool


class OperationalRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    severity: RiskSeverity
    area: EvaluationArea
    summary: str
    related_eval_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    total_unique_evidence: int = Field(ge=0)
    missing_required: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    stale_or_weak_count: int = Field(ge=0)
    source_lineage_complete: bool


class RiskEvidenceSummary(BaseModel):
    """Operational facts only; no model reasoning or scratchpad exists in the shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_id: str
    subject_version: str
    correlation_id: str
    completion: CompletionSummary
    quality_findings: tuple[str, ...]
    risks: tuple[OperationalRisk, ...]
    evidence: EvidenceSummary
    blocking_eval_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    readiness: AIReadinessStatus
    operational_recommendation: str


class RiskEvidenceSummaryBuilder:
    def build(
        self,
        suite: EvaluationSuiteResult,
        readiness: AIReadinessAssessment,
    ) -> RiskEvidenceSummary:
        missing = tuple(
            item
            for item in suite.case_results
            if item.outcome is EvaluationOutcome.NOT_RUN
            or "MISSING" in " ".join(item.evidence.reason_codes)
        )
        invalid = sum(
            "INVALID" in " ".join(item.evidence.reason_codes) for item in suite.case_results
        )
        weak = sum(
            any(token in " ".join(item.evidence.reason_codes) for token in ("STALE", "WEAK"))
            for item in suite.case_results
        )
        risks = tuple(
            OperationalRisk(
                severity=self._severity(item.severity),
                area=item.area,
                summary=item.summary,
                related_eval_ids=(item.test_id,),
                evidence_ids=item.evidence.evidence_ids,
            )
            for item in suite.case_results
            if item.outcome is not EvaluationOutcome.PASS
        )
        quality_findings = tuple(
            item.summary
            for item in suite.case_results
            if item.outcome is EvaluationOutcome.FAIL
            and item.severity in {EvaluationSeverity.INFO, EvaluationSeverity.WARNING}
        )
        evidence_ids = {
            evidence_id for item in suite.case_results for evidence_id in item.evidence.evidence_ids
        } | {
            str(item.get("evidence_id")) for item in suite.evidence_refs if item.get("evidence_id")
        }
        return RiskEvidenceSummary(
            subject_id=suite.subject_id,
            subject_version=suite.subject_version,
            correlation_id=suite.correlation_id,
            completion=CompletionSummary(
                total_evals=len(suite.case_results),
                passed=suite.passed,
                failed=suite.failed,
                not_run=suite.not_run,
                required_complete=not any(item.required for item in missing),
            ),
            quality_findings=quality_findings,
            risks=risks,
            evidence=EvidenceSummary(
                total_unique_evidence=len(evidence_ids),
                missing_required=len(missing),
                invalid_count=invalid,
                stale_or_weak_count=weak,
                source_lineage_complete=not invalid and not missing,
            ),
            blocking_eval_ids=readiness.blocking_eval_ids,
            limitations=tuple(
                dict.fromkeys(
                    (
                        *suite.limitations,
                        *(
                            risk.summary
                            for risk in risks
                            if risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
                        ),
                    )
                )
            ),
            readiness=readiness.status,
            operational_recommendation=self._recommendation(readiness.status),
        )

    @staticmethod
    def _severity(severity: EvaluationSeverity) -> RiskSeverity:
        return {
            EvaluationSeverity.INFO: RiskSeverity.INFO,
            EvaluationSeverity.WARNING: RiskSeverity.MEDIUM,
            EvaluationSeverity.MATERIAL: RiskSeverity.HIGH,
            EvaluationSeverity.BLOCKER: RiskSeverity.CRITICAL,
        }[severity]

    @staticmethod
    def _recommendation(status: AIReadinessStatus) -> str:
        if status in {AIReadinessStatus.NOT_READY, AIReadinessStatus.INCOMPLETE}:
            return (
                "Return the subject for revision or complete required assurance before IT review."
            )
        if status is AIReadinessStatus.READY_WITH_FINDINGS:
            return "Submit to IT review with all non-material findings and limitations visible."
        return "Submit the package to IT review; this assessment is advisory and not approval."
