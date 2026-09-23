"""Shared deterministic assurance probe execution."""

from collections.abc import Callable

from genesis.evals.models import (
    EvaluationAssertionResult,
    EvaluationCaseResult,
    EvaluationEvidence,
    EvaluationObservation,
    EvaluationOutcome,
    EvaluationSeverity,
    EvaluationSubjectSnapshot,
    ObservationProof,
)
from genesis.evals.regression import RegressionCaseRef

ProbeEvaluator = Callable[[EvaluationObservation], tuple[bool, str, tuple[str, ...]]]


class RegisteredInvariantProbe:
    """A code-registered invariant; observed facts never carry a PASS decision."""

    def __init__(
        self,
        case_id: str,
        evaluator: ProbeEvaluator,
        observation_type: type[ObservationProof],
    ) -> None:
        self.case_id = case_id
        self._evaluator = evaluator
        self._observation_type = observation_type

    def evaluate(
        self,
        subject: EvaluationSubjectSnapshot,
        case: RegressionCaseRef,
    ) -> EvaluationCaseResult:
        observation = subject.observations.get(case.eval_case_id)
        if observation is None or not isinstance(observation, self._observation_type):
            return self._result(
                subject,
                case,
                None,
                EvaluationOutcome.NOT_RUN,
                "Required typed observation was not supplied.",
                ("EVAL_OBSERVATION_MISSING_OR_WRONG_TYPE",),
            )
        passed, observed, reason_codes = self._evaluator(observation)
        outcome = EvaluationOutcome.PASS if passed else EvaluationOutcome.FAIL
        if (
            outcome is EvaluationOutcome.PASS
            and case.criticality in {EvaluationSeverity.MATERIAL, EvaluationSeverity.BLOCKER}
            and not (
                observation.evidence_ids or observation.evidence_refs or observation.fixture_ids
            )
        ):
            return self._result(
                subject,
                case,
                observation,
                EvaluationOutcome.NOT_RUN,
                "Material invariant passed logically but has no observable proof artifact.",
                ("MATERIAL_PASS_PROOF_MISSING",),
            )
        return self._result(subject, case, observation, outcome, observed, reason_codes)

    @staticmethod
    def _result(
        subject: EvaluationSubjectSnapshot,
        case: RegressionCaseRef,
        observation: ObservationProof | None,
        outcome: EvaluationOutcome,
        observed: str,
        reason_codes: tuple[str, ...],
    ) -> EvaluationCaseResult:
        return EvaluationCaseResult(
            test_id=case.eval_case_id,
            area=case.area,
            taxonomy=case.taxonomy,
            outcome=outcome,
            severity=case.criticality,
            required=case.required,
            summary=observed,
            assertions=(
                EvaluationAssertionResult(
                    assertion_id=f"{case.eval_case_id}.invariant",
                    passed=outcome is EvaluationOutcome.PASS,
                    expected=case.rationale,
                    observed=observed,
                ),
            ),
            evidence=EvaluationEvidence(
                evidence_ids=observation.evidence_ids if observation else (),
                evidence_refs=observation.evidence_refs if observation else (),
                fixture_ids=observation.fixture_ids if observation else (),
                reason_codes=reason_codes,
                observations=(observed,),
            ),
            limitations=observation.limitations if observation else (observed,),
            correlation_id=subject.correlation_id,
            subject_id=subject.subject_id,
            subject_version=subject.subject_version,
        )
