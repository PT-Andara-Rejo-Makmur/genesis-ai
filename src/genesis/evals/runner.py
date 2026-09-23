"""Deterministic execution of registered, typed H8 evaluation probes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from genesis.evals.models import (
    EvaluationAssertionResult,
    EvaluationCaseResult,
    EvaluationEvidence,
    EvaluationOutcome,
    EvaluationSubjectSnapshot,
    EvaluationSuiteResult,
)
from genesis.evals.probes import registered_probes
from genesis.evals.regression import RegressionCaseRef, RegressionSetProposal
from genesis.evals.research import RDSafetyEvaluator


class EvaluationProbe(Protocol):
    case_id: str

    def evaluate(
        self,
        subject: EvaluationSubjectSnapshot,
        case: RegressionCaseRef,
    ) -> EvaluationCaseResult: ...


class EvaluationRunner:
    """Runs only constructor-registered probes in regression-set order."""

    def __init__(self, probes: Iterable[EvaluationProbe]) -> None:
        by_id: dict[str, EvaluationProbe] = {}
        for probe in probes:
            if probe.case_id in by_id:
                raise ValueError(f"Duplicate evaluation probe ID: {probe.case_id}")
            by_id[probe.case_id] = probe
        self._probes: Mapping[str, EvaluationProbe] = by_id

    @classmethod
    def for_regression_set(
        cls,
        proposal: RegressionSetProposal,
        *,
        research_evaluator: RDSafetyEvaluator | None = None,
    ) -> EvaluationRunner:
        return cls(registered_probes(proposal, research_evaluator=research_evaluator))

    def run(
        self,
        proposal: RegressionSetProposal,
        subject: EvaluationSubjectSnapshot,
    ) -> EvaluationSuiteResult:
        results: list[EvaluationCaseResult] = []
        for case in proposal.case_refs:
            probe = self._probes.get(case.eval_case_id)
            if probe is None:
                results.append(self._not_run(subject, case, "EVAL_PROBE_NOT_REGISTERED"))
                continue
            try:
                results.append(probe.evaluate(subject, case))
            except Exception as exc:  # probe isolation is part of the assurance boundary
                results.append(
                    self._not_run(
                        subject,
                        case,
                        "EVAL_PROBE_EXCEPTION",
                        limitation=f"Probe failed safely: {type(exc).__name__}.",
                    )
                )
        refs: dict[str, dict[str, object]] = {}
        for result in results:
            for ref in result.evidence.evidence_refs:
                evidence_id = str(ref.get("evidence_id", ""))
                if evidence_id:
                    refs.setdefault(evidence_id, ref)
        material_failures = tuple(
            item.test_id
            for item in results
            if item.outcome is EvaluationOutcome.FAIL
            and item.severity.value in {"MATERIAL", "BLOCKER"}
        )
        limitations = tuple(dict.fromkeys(value for item in results for value in item.limitations))
        return EvaluationSuiteResult(
            suite_id=proposal.regression_set_id,
            suite_version=proposal.version,
            subject_id=subject.subject_id,
            subject_version=subject.subject_version,
            tenant_id=subject.tenant_id,
            organization_id=subject.organization_id,
            workspace_id=subject.workspace_id,
            correlation_id=subject.correlation_id,
            case_results=tuple(results),
            passed=sum(item.outcome is EvaluationOutcome.PASS for item in results),
            failed=sum(item.outcome is EvaluationOutcome.FAIL for item in results),
            not_run=sum(item.outcome is EvaluationOutcome.NOT_RUN for item in results),
            material_failure_ids=material_failures,
            evidence_refs=tuple(refs.values()),
            limitations=limitations,
        )

    @staticmethod
    def _not_run(
        subject: EvaluationSubjectSnapshot,
        case: RegressionCaseRef,
        reason_code: str,
        *,
        limitation: str = "Registered evaluation probe is unavailable.",
    ) -> EvaluationCaseResult:
        return EvaluationCaseResult(
            test_id=case.eval_case_id,
            area=case.area,
            taxonomy=case.taxonomy,
            outcome=EvaluationOutcome.NOT_RUN,
            severity=case.criticality,
            required=case.required,
            summary=limitation,
            assertions=(
                EvaluationAssertionResult(
                    assertion_id=f"{case.eval_case_id}.executed",
                    passed=False,
                    expected="Registered probe executes successfully.",
                    observed=limitation,
                ),
            ),
            evidence=EvaluationEvidence(reason_codes=(reason_code,)),
            limitations=(limitation,),
            correlation_id=subject.correlation_id,
            subject_id=subject.subject_id,
            subject_version=subject.subject_version,
        )
