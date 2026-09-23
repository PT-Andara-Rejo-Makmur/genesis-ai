"""Deterministic and monotonic AI readiness policy."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from genesis.evals.models import EvaluationOutcome, EvaluationSeverity, EvaluationSuiteResult


class AIReadinessStatus(StrEnum):
    READY_FOR_IT_REVIEW = "READY_FOR_IT_REVIEW"
    READY_WITH_FINDINGS = "READY_WITH_FINDINGS"
    NOT_READY = "NOT_READY"
    INCOMPLETE = "INCOMPLETE"


class AIReadinessAssessment(BaseModel):
    """Advisory AI-local readiness; never an approval or release decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: AIReadinessStatus
    blocking_eval_ids: tuple[str, ...]
    finding_eval_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


class DeterministicReadinessPolicy:
    def assess(self, suite: EvaluationSuiteResult) -> AIReadinessAssessment:
        required_not_run = tuple(
            item.test_id
            for item in suite.case_results
            if item.required and item.outcome is EvaluationOutcome.NOT_RUN
        )
        failures = tuple(
            item.test_id
            for item in suite.case_results
            if item.required
            and item.outcome is EvaluationOutcome.FAIL
            and item.severity in {EvaluationSeverity.MATERIAL, EvaluationSeverity.BLOCKER}
        )
        findings = tuple(
            item.test_id
            for item in suite.case_results
            if item.outcome is EvaluationOutcome.FAIL and item.test_id not in failures
        )
        if failures:
            return AIReadinessAssessment(
                status=AIReadinessStatus.NOT_READY,
                blocking_eval_ids=failures,
                finding_eval_ids=findings,
                reason_codes=("REQUIRED_MATERIAL_EVAL_FAILED",),
            )
        if required_not_run:
            return AIReadinessAssessment(
                status=AIReadinessStatus.INCOMPLETE,
                blocking_eval_ids=required_not_run,
                finding_eval_ids=findings,
                reason_codes=("REQUIRED_EVAL_NOT_RUN",),
            )
        if findings:
            return AIReadinessAssessment(
                status=AIReadinessStatus.READY_WITH_FINDINGS,
                blocking_eval_ids=(),
                finding_eval_ids=findings,
                reason_codes=("NON_MATERIAL_FINDINGS_PRESENT",),
            )
        return AIReadinessAssessment(
            status=AIReadinessStatus.READY_FOR_IT_REVIEW,
            blocking_eval_ids=(),
            finding_eval_ids=(),
            reason_codes=("ALL_REQUIRED_EVALS_PASSED",),
        )
