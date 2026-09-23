"""Deterministic and monotonic AI readiness policy."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from genesis.evals.models import EvaluationOutcome, EvaluationSeverity, EvaluationSuiteResult
from genesis.evals.regression import RegressionSetProposal


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


class RegressionCompleteness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_suite_id: str
    expected_suite_version: str
    suite_identity_matches: bool
    expected_case_ids: tuple[str, ...]
    actual_case_ids: tuple[str, ...]
    missing_required_ids: tuple[str, ...]
    unexpected_ids: tuple[str, ...]
    mismatched_case_ids: tuple[str, ...]
    complete: bool


class DeterministicReadinessPolicy:
    def completeness(
        self,
        proposal: RegressionSetProposal,
        suite: EvaluationSuiteResult,
    ) -> RegressionCompleteness:
        expected = tuple(item.eval_case_id for item in proposal.case_refs)
        required = {item.eval_case_id for item in proposal.case_refs if item.required}
        actual = tuple(item.test_id for item in suite.case_results)
        actual_set = set(actual)
        identity_matches = (
            suite.suite_id == proposal.regression_set_id and suite.suite_version == proposal.version
        )
        missing = tuple(item for item in expected if item in required and item not in actual_set)
        unexpected = tuple(item for item in actual if item not in set(expected))
        expected_by_id = {item.eval_case_id: item for item in proposal.case_refs}
        mismatched = tuple(
            item.test_id
            for item in suite.case_results
            if item.test_id in expected_by_id
            and (
                item.area != expected_by_id[item.test_id].area
                or item.taxonomy != expected_by_id[item.test_id].taxonomy
                or item.severity != expected_by_id[item.test_id].criticality
                or item.required != expected_by_id[item.test_id].required
            )
        )
        return RegressionCompleteness(
            expected_suite_id=proposal.regression_set_id,
            expected_suite_version=proposal.version,
            suite_identity_matches=identity_matches,
            expected_case_ids=expected,
            actual_case_ids=actual,
            missing_required_ids=missing,
            unexpected_ids=unexpected,
            mismatched_case_ids=mismatched,
            complete=identity_matches and not missing and not unexpected and not mismatched,
        )

    def assess_against(
        self,
        proposal: RegressionSetProposal,
        suite: EvaluationSuiteResult,
    ) -> AIReadinessAssessment:
        completeness = self.completeness(proposal, suite)
        if not completeness.complete:
            blockers = completeness.missing_required_ids
            if not blockers and not completeness.suite_identity_matches:
                blockers = ("H8_REGRESSION_SUITE_IDENTITY_MISMATCH",)
            if not blockers and completeness.unexpected_ids:
                blockers = completeness.unexpected_ids
            if not blockers and completeness.mismatched_case_ids:
                blockers = completeness.mismatched_case_ids
            return AIReadinessAssessment(
                status=AIReadinessStatus.INCOMPLETE,
                blocking_eval_ids=blockers,
                finding_eval_ids=(),
                reason_codes=("REQUIRED_REGRESSION_SET_INCOMPLETE",),
            )
        return self.assess(suite)

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
