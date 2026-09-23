"""Canonical advisory ReviewPackage assembly without governance authority."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from genesis.contracts import CanonicalContractCatalog
from genesis.evals import (
    MVP2_H8_REGRESSION_SET,
    AIReadinessStatus,
    DeterministicReadinessPolicy,
    EvaluationArea,
    EvaluationOutcome,
    EvaluationSuiteResult,
)
from genesis.reviews.models import ReviewSubjectSnapshot, ReviewType
from genesis.reviews.projector import CanonicalAIReviewProjector
from genesis.reviews.summary import RiskEvidenceSummary

EVIDENCE_REF_SCHEMA = "https://schemas.alos.dev/v1/evidence/evidence-ref.schema.json"
REVIEW_PACKAGE_SCHEMA = "https://schemas.alos.dev/v1/review/review-package.schema.json"

_REVIEW_AREAS: dict[ReviewType, frozenset[EvaluationArea]] = {
    ReviewType.BUSINESS: frozenset({EvaluationArea.RESEARCH}),
    ReviewType.TECHNICAL: frozenset(
        {
            EvaluationArea.SKILL,
            EvaluationArea.MEMORY,
            EvaluationArea.RUNTIME,
            EvaluationArea.DELEGATION,
        }
    ),
    ReviewType.SECURITY: frozenset(
        {
            EvaluationArea.CONTEXT,
            EvaluationArea.RUNTIME,
            EvaluationArea.DELEGATION,
            EvaluationArea.RESEARCH,
        }
    ),
    ReviewType.EVIDENCE: frozenset(
        {
            EvaluationArea.CONTEXT,
            EvaluationArea.SKILL,
            EvaluationArea.MEMORY,
            EvaluationArea.RESEARCH,
        }
    ),
    ReviewType.COST_RISK: frozenset(
        {EvaluationArea.RUNTIME, EvaluationArea.DELEGATION, EvaluationArea.RESEARCH}
    ),
}


class ReviewPackageAssemblyError(ValueError):
    pass


class ReviewPackageAssembler:
    def __init__(
        self,
        *,
        contracts: CanonicalContractCatalog,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._contracts = contracts
        self._review_projector = CanonicalAIReviewProjector(contracts)
        self._clock = clock or (lambda: datetime.now(UTC))

    def assemble(
        self,
        *,
        subject: ReviewSubjectSnapshot,
        suite: EvaluationSuiteResult,
        summary: RiskEvidenceSummary,
    ) -> dict[str, Any]:
        self._validate_trace(subject, suite, summary)
        if (
            suite.suite_id != MVP2_H8_REGRESSION_SET.regression_set_id
            or suite.suite_version != MVP2_H8_REGRESSION_SET.version
        ):
            raise ReviewPackageAssemblyError("REVIEW_SUITE_REGRESSION_SET_MISMATCH")
        strict_readiness = DeterministicReadinessPolicy().assess_against(
            MVP2_H8_REGRESSION_SET, suite
        )
        self._validate_summary_consistency(suite, summary, strict_readiness)
        evidence = self._validated_evidence(subject, suite)
        if not evidence:
            raise ReviewPackageAssemblyError("REVIEW_EVIDENCE_REQUIRED")
        reviews = {
            review_type: self._review(review_type, subject, suite, summary, evidence)
            for review_type in ReviewType
        }
        qa_pass = strict_readiness.status in {
            AIReadinessStatus.READY_FOR_IT_REVIEW,
            AIReadinessStatus.READY_WITH_FINDINGS,
        } and all(
            review["status"] not in {"NOT_RUN", "FAIL", "BLOCKED_BY_EVIDENCE"}
            for review in reviews.values()
        )
        findings = tuple(
            item.test_id
            for item in suite.case_results
            if item.outcome is not EvaluationOutcome.PASS
        )
        payload: dict[str, Any] = {
            "identity": {
                "review_id": subject.review_id,
                "tenant_id": subject.tenant_id,
                **(
                    {"organization_id": subject.organization_id}
                    if subject.organization_id is not None
                    else {}
                ),
                "workspace_id": subject.workspace_id,
                "correlation_id": subject.correlation_id,
                "subject_id": subject.subject_id,
                "subject_version": subject.subject_version,
            },
            "purpose": subject.purpose,
            "materiality": subject.materiality,
            "business_context": subject.business_context,
            "capability": subject.capability,
            "scope": list(subject.scope),
            "permissions": list(subject.permissions),
            "skills": list(subject.skills),
            "tools": list(subject.tools),
            "model_policy": subject.model_policy,
            "delegation_policy": subject.delegation_policy,
            "execution_budget": subject.execution_budget,
            "automated_qa": {
                "status": "PASS" if qa_pass else "FAIL",
                "checks": [item.test_id for item in suite.case_results],
            },
            "business_ai_review": reviews[ReviewType.BUSINESS],
            "technical_ai_review": reviews[ReviewType.TECHNICAL],
            "security_ai_review": reviews[ReviewType.SECURITY],
            "evidence_ai_review": reviews[ReviewType.EVIDENCE],
            "cost_risk_ai_review": reviews[ReviewType.COST_RISK],
            "findings": list(findings),
            "risks": [item.summary for item in summary.risks],
            "limitations": list(summary.limitations),
            "ai_recommendation": {
                "recommendation_id": f"recommendation.{subject.review_id}",
                "summary": "Advisory AI assurance recommendation for human IT review.",
                "recommended_action": summary.operational_recommendation,
                "confidence": 0.8 if qa_pass else 0.2,
                "author_type": "AI",
                "finding_ids": list(findings),
                "evidence_refs": evidence,
                "limitations": list(summary.limitations) or ["HUMAN_IT_REVIEW_REQUIRED"],
                "backlog_candidate": False,
            },
            "evidence_refs": evidence,
        }
        # Authoritative it_decision/director_decision keys are intentionally impossible here.
        return self._contracts.validate(REVIEW_PACKAGE_SCHEMA, payload)

    def _review(
        self,
        review_type: ReviewType,
        subject: ReviewSubjectSnapshot,
        suite: EvaluationSuiteResult,
        summary: RiskEvidenceSummary,
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relevant = tuple(
            item for item in suite.case_results if item.area in _REVIEW_AREAS[review_type]
        )
        material_failed = tuple(
            item
            for item in relevant
            if item.outcome is EvaluationOutcome.FAIL
            and item.severity.value in {"MATERIAL", "BLOCKER"}
        )
        non_material_failed = tuple(
            item
            for item in relevant
            if item.outcome is EvaluationOutcome.FAIL and item.severity.value in {"INFO", "WARNING"}
        )
        not_run = tuple(item for item in relevant if item.outcome is EvaluationOutcome.NOT_RUN)
        if not relevant:
            status = "NOT_RUN"
        elif not_run:
            status = "BLOCKED_BY_EVIDENCE" if review_type is ReviewType.EVIDENCE else "NOT_RUN"
        elif material_failed:
            status = "FAIL"
        elif non_material_failed:
            status = "PASS_WITH_FINDINGS"
        else:
            status = "PASS"
        finding_ids = [item.test_id for item in (*material_failed, *non_material_failed, *not_run)]
        payload = {
            "review_id": f"{subject.review_id}.{review_type.value.lower()}",
            "correlation_id": subject.correlation_id,
            "review_type": review_type.value,
            "status": status,
            "summary": (
                f"{review_type.value} AI review derived from {len(relevant)} deterministic evals; "
                f"global readiness is {summary.readiness.value}."
            ),
            "finding_ids": finding_ids,
            "recommendations": [summary.operational_recommendation],
            "evidence_refs": evidence,
            "limitations": list(
                dict.fromkeys(value for item in relevant for value in item.limitations)
            ),
            "completed_at": self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
        return self._review_projector.project(payload)

    def _validated_evidence(
        self,
        subject: ReviewSubjectSnapshot,
        suite: EvaluationSuiteResult,
    ) -> list[dict[str, Any]]:
        unique: dict[str, dict[str, Any]] = {}
        for raw in (*subject.evidence_refs, *suite.evidence_refs):
            canonical = self._contracts.validate(EVIDENCE_REF_SCHEMA, raw)
            if canonical.get("tenant_id") != subject.tenant_id:
                raise ReviewPackageAssemblyError("REVIEW_EVIDENCE_TENANT_MISMATCH")
            if (
                subject.organization_id is not None
                and canonical.get("organization_id") != subject.organization_id
            ):
                raise ReviewPackageAssemblyError("REVIEW_EVIDENCE_ORGANIZATION_MISMATCH")
            if canonical.get("workspace_id") != subject.workspace_id:
                raise ReviewPackageAssemblyError("REVIEW_EVIDENCE_WORKSPACE_MISMATCH")
            unique.setdefault(str(canonical["evidence_id"]), canonical)
        return list(unique.values())

    @staticmethod
    def _validate_trace(
        subject: ReviewSubjectSnapshot,
        suite: EvaluationSuiteResult,
        summary: RiskEvidenceSummary,
    ) -> None:
        expected = (subject.subject_id, subject.subject_version, subject.correlation_id)
        if (suite.subject_id, suite.subject_version, suite.correlation_id) != expected:
            raise ReviewPackageAssemblyError("REVIEW_SUITE_SUBJECT_MISMATCH")
        if (summary.subject_id, summary.subject_version, summary.correlation_id) != expected:
            raise ReviewPackageAssemblyError("REVIEW_SUMMARY_SUBJECT_MISMATCH")
        if (
            suite.tenant_id != subject.tenant_id
            or suite.organization_id != subject.organization_id
            or suite.workspace_id != subject.workspace_id
        ):
            raise ReviewPackageAssemblyError("REVIEW_SUITE_IDENTITY_MISMATCH")

    @staticmethod
    def _validate_summary_consistency(
        suite: EvaluationSuiteResult,
        summary: RiskEvidenceSummary,
        strict_readiness: Any,
    ) -> None:
        if summary.readiness is not strict_readiness.status:
            raise ReviewPackageAssemblyError("REVIEW_SUMMARY_READINESS_MISMATCH")
        if summary.blocking_eval_ids != strict_readiness.blocking_eval_ids:
            raise ReviewPackageAssemblyError("REVIEW_SUMMARY_BLOCKERS_MISMATCH")
        if (
            summary.completion.total_evals != len(suite.case_results)
            or summary.completion.passed != suite.passed
            or summary.completion.failed != suite.failed
            or summary.completion.not_run != suite.not_run
        ):
            raise ReviewPackageAssemblyError("REVIEW_SUMMARY_COUNTS_MISMATCH")
        if not set(suite.material_failure_ids).issubset(summary.blocking_eval_ids):
            raise ReviewPackageAssemblyError("REVIEW_SUMMARY_MATERIAL_FAILURE_HIDDEN")
