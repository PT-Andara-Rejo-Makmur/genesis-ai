from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.evals import (
    MVP2_H8_REGRESSION_SET,
    AIReadinessStatus,
    DeterministicReadinessPolicy,
    EvaluationArea,
    EvaluationOutcome,
    EvaluationRunner,
    EvaluationSeverity,
    EvaluationSubjectSnapshot,
    EvaluationTaxonomy,
    MaterialBehaviorObservation,
    RegressionCaseRef,
    RegressionSetProposal,
)
from genesis.evals.research import RDSafetyEvaluator
from genesis.research.models import ResearchDomain
from genesis.research.orchestration import (
    ClaimAssessment,
    ClaimKind,
    EvidenceAdmissionAssessment,
    EvidenceNeed,
    EvidenceQualityAssessment,
    EvidenceRelevance,
    EvidenceRelevanceAssessment,
    EvidenceUsability,
    ModelCallUsage,
    QualityTier,
    ResearchEvidenceItem,
    ResearchFindingAnalysis,
    ResearchOrchestrationResult,
    ResearchPlan,
    ResearchRecommendationAnalysis,
    ResearchSubquery,
    RetrievalAttempt,
    RetrievalStatus,
    SourceMode,
)
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.research.tool_selection import ResearchToolCategory
from genesis.reviews import (
    ReviewPackageAssembler,
    ReviewPackageAssemblyError,
    ReviewSubjectSnapshot,
    RiskEvidenceSummaryBuilder,
)

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def evidence_ref(evidence_id: str = "evidence.h8.001", **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tenant_id": "tenant.h8",
        "organization_id": "organization.h8",
        "workspace_id": "workspace.h8",
        "correlation_id": "correlation.h8",
        "scope_refs": ["scope.h8"],
        "evidence_id": evidence_id,
        "source_id": f"source.{evidence_id}",
        "uri": f"https://example.test/{evidence_id}",
        "captured_at": "2026-09-23T00:00:00Z",
        "content_hash": "sha256:" + "a" * 64,
        "source_version": "1.0.0",
        "data_classification": "INTERNAL",
        "source_type": "INTERNAL",
        "freshness": "CURRENT",
        "reliability": "HIGH",
        "content_trust": "GOVERNED",
        "instruction_authority": False,
        "validation_status": "VALID",
    }
    payload.update(changes)
    return payload


def proposal(*cases: RegressionCaseRef) -> RegressionSetProposal:
    return RegressionSetProposal(
        regression_set_id="test.h8.suite",
        version="1.0.0",
        purpose="Test deterministic assurance.",
        subject_types=("AGENT",),
        case_refs=cases,
        created_from_milestone="MVP2-H8",
    )


def case(
    case_id: str,
    *,
    severity: EvaluationSeverity = EvaluationSeverity.MATERIAL,
    required: bool = True,
) -> RegressionCaseRef:
    return RegressionCaseRef(
        eval_case_id=case_id,
        area=EvaluationArea.CONTEXT,
        taxonomy=EvaluationTaxonomy.SECURITY,
        criticality=severity,
        rationale="The invariant must hold.",
        required=required,
    )


def subject(**observations: MaterialBehaviorObservation) -> EvaluationSubjectSnapshot:
    return EvaluationSubjectSnapshot(
        subject_id="agent.h8",
        subject_version="1.2.3",
        tenant_id="tenant.h8",
        organization_id="organization.h8",
        workspace_id="workspace.h8",
        correlation_id="correlation.h8",
        observations=observations,
    )


def observation(
    passed: bool,
    *,
    evidence: bool = True,
    reason: str = "OBSERVED_INVARIANT",
) -> MaterialBehaviorObservation:
    return MaterialBehaviorObservation(
        passed=passed,
        observed="Invariant observed as expected." if passed else "Invariant violation observed.",
        reason_codes=(reason,),
        evidence_refs=(evidence_ref(),) if evidence else (),
        evidence_ids=("evidence.h8.001",) if evidence else (),
        fixture_ids=("fixture.h8.001",),
    )


def test_runner_is_registered_repeatable_and_fail_closed() -> None:
    regression = proposal(case("eval.pass"), case("eval.fail"), case("eval.missing"))
    runner = EvaluationRunner.for_regression_set(regression)
    snapshot = subject(**{"eval.pass": observation(True), "eval.fail": observation(False)})

    first = runner.run(regression, snapshot)
    second = runner.run(regression, snapshot)

    assert [item.test_id for item in first.case_results] == [
        "eval.pass",
        "eval.fail",
        "eval.missing",
    ]
    assert [item.outcome for item in first.case_results] == [
        EvaluationOutcome.PASS,
        EvaluationOutcome.FAIL,
        EvaluationOutcome.NOT_RUN,
    ]
    assert first == second
    assert first.subject_version == "1.2.3"
    assert first.correlation_id == "correlation.h8"


def test_runner_rejects_duplicate_probe_ids_and_isolates_probe_exception() -> None:
    regression = proposal(case("eval.exception"))

    class BrokenProbe:
        case_id = "eval.exception"

        def evaluate(self, *_: object) -> object:
            raise RuntimeError("synthetic failure")

    with pytest.raises(ValueError, match="Duplicate"):
        EvaluationRunner((BrokenProbe(), BrokenProbe()))
    suite = EvaluationRunner((BrokenProbe(),)).run(regression, subject())
    assert suite.case_results[0].outcome is EvaluationOutcome.NOT_RUN
    assert suite.case_results[0].evidence.reason_codes == ("EVAL_PROBE_EXCEPTION",)


def test_readiness_is_deterministic_and_monotonic() -> None:
    passing = proposal(case("eval.pass"))
    pass_suite = EvaluationRunner.for_regression_set(passing).run(
        passing, subject(**{"eval.pass": observation(True)})
    )
    policy = DeterministicReadinessPolicy()
    assert policy.assess(pass_suite).status is AIReadinessStatus.READY_FOR_IT_REVIEW

    failed = proposal(case("eval.pass"), case("eval.blocker", severity=EvaluationSeverity.BLOCKER))
    fail_suite = EvaluationRunner.for_regression_set(failed).run(
        failed,
        subject(
            **{
                "eval.pass": observation(True),
                "eval.blocker": observation(False),
            }
        ),
    )
    assessment = policy.assess(fail_suite)
    assert assessment.status is AIReadinessStatus.NOT_READY
    assert assessment.blocking_eval_ids == ("eval.blocker",)
    assert "force_ready" not in DeterministicReadinessPolicy.assess.__annotations__

    incomplete = proposal(case("eval.required"))
    incomplete_suite = EvaluationRunner.for_regression_set(incomplete).run(incomplete, subject())
    assert policy.assess(incomplete_suite).status is AIReadinessStatus.INCOMPLETE

    warning = proposal(case("eval.warning", severity=EvaluationSeverity.WARNING, required=False))
    warning_suite = EvaluationRunner.for_regression_set(warning).run(
        warning, subject(**{"eval.warning": observation(False)})
    )
    assert policy.assess(warning_suite).status is AIReadinessStatus.READY_WITH_FINDINGS


def test_regression_catalog_is_stable_and_covers_all_material_areas() -> None:
    ids = tuple(item.eval_case_id for item in MVP2_H8_REGRESSION_SET.case_refs)
    assert MVP2_H8_REGRESSION_SET.regression_set_id == "mvp2-h8-rc1-ai-regression"
    assert MVP2_H8_REGRESSION_SET.version == "1.0.0"
    assert len(ids) == len(set(ids))
    assert tuple(sorted(set(item.area for item in MVP2_H8_REGRESSION_SET.case_refs))) == tuple(
        sorted(EvaluationArea)
    )
    assert ids[0] == "h8.context.scoped-valid"
    assert ids[-1] == "h8.research.domain-quality"


def review_subject() -> ReviewSubjectSnapshot:
    return ReviewSubjectSnapshot(
        review_id="review.h8.001",
        subject_id="agent.h8",
        subject_version="1.2.3",
        tenant_id="tenant.h8",
        organization_id="organization.h8",
        workspace_id="workspace.h8",
        correlation_id="correlation.h8",
        purpose="Assure the exact H8 subject before human IT review.",
        materiality="MATERIAL",
        business_context={"domain": "TECHNOLOGY"},
        capability={
            "capability_id": "capability.h8",
            "version": "1.2.3",
            "name": "H8 assurance",
            "purpose": "Assure material behavior.",
            "owner": "actor.h8",
            "capability_type": "AGENT",
            "output_state": "NEEDS_REVIEW",
            "lifecycle_state": "DRAFT",
            "scope_refs": ["scope.h8"],
        },
        scope=("scope.h8",),
        permissions=("review.read",),
        model_policy={"gateway_required": True, "policy_ref": "policy.h8"},
        delegation_policy={"enabled": False, "lineage_required": True, "max_depth": 0},
        execution_budget={"max_tokens": 1000, "max_steps": 4},
        evidence_refs=(evidence_ref(),),
    )


def test_summary_and_canonical_review_package_keep_failures_visible() -> None:
    regression = proposal(case("eval.material"))
    suite = EvaluationRunner.for_regression_set(regression).run(
        regression, subject(**{"eval.material": observation(False)})
    )
    readiness = DeterministicReadinessPolicy().assess(suite)
    summary = RiskEvidenceSummaryBuilder().build(suite, readiness)
    assert summary.blocking_eval_ids == ("eval.material",)
    assert summary.risks[0].related_eval_ids == ("eval.material",)
    assert "reasoning" not in summary.model_dump()

    package = ReviewPackageAssembler(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        clock=lambda: datetime(2026, 9, 23, tzinfo=UTC),
    ).assemble(subject=review_subject(), suite=suite, summary=summary)
    assert package["identity"]["subject_version"] == "1.2.3"
    assert package["automated_qa"]["status"] == "FAIL"
    assert package["evidence_ai_review"]["status"] == "FAIL"
    assert "it_decision" not in package
    assert "director_decision" not in package
    assert set(key for key in package if key.endswith("_ai_review")) == {
        "business_ai_review",
        "technical_ai_review",
        "security_ai_review",
        "evidence_ai_review",
        "cost_risk_ai_review",
    }


def test_canonical_review_package_pass_is_advisory_only() -> None:
    regression = proposal(case("eval.pass"))
    suite = EvaluationRunner.for_regression_set(regression).run(
        regression, subject(**{"eval.pass": observation(True)})
    )
    readiness = DeterministicReadinessPolicy().assess(suite)
    summary = RiskEvidenceSummaryBuilder().build(suite, readiness)
    package = ReviewPackageAssembler(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        clock=lambda: datetime(2026, 9, 23, tzinfo=UTC),
    ).assemble(subject=review_subject(), suite=suite, summary=summary)
    assert package["automated_qa"]["status"] == "PASS"
    assert package["ai_recommendation"]["author_type"] == "AI"
    assert "IT review" in package["ai_recommendation"]["recommended_action"]
    assert "it_decision" not in package
    assert "director_decision" not in package


def test_review_package_rejects_missing_or_cross_tenant_evidence() -> None:
    regression = proposal(case("eval.pass"))
    suite = EvaluationRunner.for_regression_set(regression).run(
        regression, subject(**{"eval.pass": observation(True, evidence=False)})
    )
    readiness = DeterministicReadinessPolicy().assess(suite)
    summary = RiskEvidenceSummaryBuilder().build(suite, readiness)
    assembler = ReviewPackageAssembler(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))

    with pytest.raises(ReviewPackageAssemblyError, match="EVIDENCE_REQUIRED"):
        assembler.assemble(
            subject=review_subject().model_copy(update={"evidence_refs": ()}),
            suite=suite,
            summary=summary,
        )
    with pytest.raises(ReviewPackageAssemblyError, match="TENANT_MISMATCH"):
        assembler.assemble(
            subject=review_subject().model_copy(
                update={"evidence_refs": (evidence_ref(tenant_id="tenant.other"),)}
            ),
            suite=suite,
            summary=summary,
        )


def research_result(domain: ResearchDomain) -> ResearchOrchestrationResult:
    evidence = ResearchEvidenceItem(
        evidence_ref=evidence_ref(),
        content="Current cited evidence supports a governed scenario and human review.",
        category=ResearchToolCategory.INTERNAL_DOCUMENT,
        subquery_ids=("subquery.h8",),
    )
    claim = ClaimAssessment(
        claim_id="claim.h8.fact",
        normalized_topic="governed scenario",
        statement="The current evidence supports a bounded scenario.",
        kind=ClaimKind.FACT,
        evidence_ids=(evidence.evidence_id,),
        source_ids=(evidence.source_id,),
        source_versions=("1.0.0",),
        confidence=0.8,
    )
    finding = ResearchFindingAnalysis(
        finding_id="finding.h8",
        domain=domain,
        statement=claim.statement,
        fact_claim_ids=(claim.claim_id,),
        evidence_ids=(evidence.evidence_id,),
        confidence=0.8,
        quality_reasons=("CURRENT_HIGH_RELIABILITY",),
    )
    action = {
        ResearchDomain.TECHNOLOGY: (
            "Run a governed security compatibility benchmark proof of concept."
        ),
        ResearchDomain.PROPERTY_BUSINESS: (
            "Run a pricing scenario and unit economics validation review."
        ),
        ResearchDomain.MANAGEMENT: (
            "Pilot the SOP KPI governance control through management review."
        ),
        ResearchDomain.PROPERTY_MARKET: (
            "Perform market comparable site due diligence and region sensitivity review."
        ),
    }[domain]
    recommendation = ResearchRecommendationAnalysis(
        recommendation_id="recommendation.h8",
        finding_ids=(finding.finding_id,),
        fact_claim_ids=(claim.claim_id,),
        proposed_action=action,
        confidence=0.7,
        evidence_ids=(evidence.evidence_id,),
        limitations=("HUMAN_REVIEW_REQUIRED",),
    )
    subquery = ResearchSubquery(
        subquery_id="subquery.h8",
        question="What material evidence supports this governed review?",
        domain=domain,
        evidence_need=EvidenceNeed.CURRENT_STATE,
        preferred_source_categories=(ResearchToolCategory.INTERNAL_DOCUMENT,),
        required_scope_refs=("scope.h8",),
        reason_code="MATERIAL_EVIDENCE_REQUIRED",
    )
    return ResearchOrchestrationResult(
        plan=ResearchPlan(
            research_id="research.h8",
            domain=domain,
            original_question=subquery.question,
            subqueries=(subquery,),
            max_subqueries=1,
        ),
        source_mode=SourceMode.INTERNAL_ONLY,
        retrieval_attempts=(),
        evidence_items=(evidence,),
        evidence_admissions=(
            EvidenceAdmissionAssessment(
                evidence_id=evidence.evidence_id,
                admitted=True,
                reason_codes=("CANONICAL_EVIDENCE_ADMITTED",),
            ),
        ),
        relevance_assessments=(
            EvidenceRelevanceAssessment(
                evidence_id=evidence.evidence_id,
                subquery_id=subquery.subquery_id,
                relevance=EvidenceRelevance.EXACT,
                reason_codes=("EXPLICIT_SUBQUERY_MATCH",),
                score=1,
            ),
        ),
        evidence_assessments=(
            EvidenceQualityAssessment(
                evidence_id=evidence.evidence_id,
                tier=QualityTier.STRONG,
                freshness=FreshnessStatus.CURRENT,
                reliability=SourceReliability.HIGH,
                usability=EvidenceUsability.PRIMARY,
                reason_codes=("CURRENT_HIGH_RELIABILITY",),
                confidence_cap=0.9,
            ),
        ),
        claims=(claim,),
        duplicates=(),
        corroborations=(),
        conflicts=(),
        assumptions=(),
        gaps=(),
        findings=(finding,),
        recommendations=(recommendation,),
        canonical_result={},
        limitations=("HUMAN_REVIEW_REQUIRED",),
        usage=ModelCallUsage(),
    )


@pytest.mark.parametrize("domain", tuple(ResearchDomain))
def test_one_rd_safety_evaluator_covers_all_four_domains(domain: ResearchDomain) -> None:
    evaluator = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    evaluation = evaluator.evaluate(research_result(domain))
    assert evaluation.domain is domain
    assert evaluation.passed
    assert {item.check_id for item in evaluation.checks} >= {
        "rd.canonical-lineage",
        "rd.citation-complete",
        "rd.external-trust",
        "rd.freshness",
        "rd.conflicts",
        "rd.assumptions",
        "rd.safe-failure",
        "rd.domain-quality",
    }


def test_rd_safety_fails_unknown_citation_and_authority_wording() -> None:
    evaluator = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    valid = research_result(ResearchDomain.TECHNOLOGY)
    broken_finding = valid.findings[0].model_copy(update={"evidence_ids": ("evidence.unknown",)})
    broken_recommendation = valid.recommendations[0].model_copy(
        update={"proposed_action": "Approve and activate the ModelGateway configuration."}
    )
    evaluation = evaluator.evaluate(
        valid.model_copy(
            update={
                "findings": (broken_finding,),
                "recommendations": (broken_recommendation,),
            }
        )
    )
    assert not evaluation.passed
    failed = {item.check_id for item in evaluation.checks if not item.passed}
    assert "rd.citation-complete" in failed
    assert "rd.advisory-only" in failed


def test_external_research_requires_canonical_untrusted_lineage() -> None:
    evaluator = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    valid = research_result(ResearchDomain.TECHNOLOGY)
    external_ref = evidence_ref(
        source_type="EXTERNAL",
        content_trust="UNTRUSTED",
        instruction_authority=False,
    )
    external_item = valid.evidence_items[0].model_copy(
        update={
            "evidence_ref": external_ref,
            "category": ResearchToolCategory.EXTERNAL_RESEARCH,
        }
    )
    external = valid.model_copy(
        update={"source_mode": SourceMode.EXTERNAL_ONLY, "evidence_items": (external_item,)}
    )
    assert evaluator.evaluate(external).passed

    missing_lineage = external_item.model_copy(
        update={
            "evidence_ref": {
                key: value for key, value in external_ref.items() if key != "source_version"
            }
        }
    )
    failed = evaluator.evaluate(external.model_copy(update={"evidence_items": (missing_lineage,)}))
    assert not failed.passed
    assert not next(
        item for item in failed.checks if item.check_id == "rd.canonical-lineage"
    ).passed

    no_external_evidence = valid.model_copy(
        update={
            "source_mode": SourceMode.EXTERNAL_ONLY,
            "evidence_items": (),
        }
    )
    external_failure = evaluator.evaluate(no_external_evidence)
    assert not next(
        item for item in external_failure.checks if item.check_id == "rd.external-evidence"
    ).passed


def test_stale_only_high_confidence_and_assumption_fact_collision_fail() -> None:
    evaluator = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))
    valid = research_result(ResearchDomain.PROPERTY_MARKET)
    stale_assessment = valid.evidence_assessments[0].model_copy(
        update={"freshness": FreshnessStatus.STALE}
    )
    colliding_assumption = valid.claims[0].model_copy(update={"kind": ClaimKind.ASSUMPTION})
    result = valid.model_copy(
        update={
            "evidence_assessments": (stale_assessment,),
            "assumptions": (colliding_assumption,),
        }
    )
    evaluation = evaluator.evaluate(result)
    failed = {item.check_id for item in evaluation.checks if not item.passed}
    assert "rd.freshness" in failed
    assert "rd.assumptions" in failed


def test_rd_safe_failure_requires_retrieval_limitation() -> None:
    valid = research_result(ResearchDomain.TECHNOLOGY)
    broken = valid.model_copy(
        update={
            "retrieval_attempts": (
                RetrievalAttempt(
                    subquery_id="subquery.h8",
                    status=RetrievalStatus.FAILED,
                    reason_codes=("PROVIDER_FAILED",),
                ),
            ),
            "limitations": ("HUMAN_REVIEW_REQUIRED",),
        }
    )
    evaluation = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT)).evaluate(
        broken
    )
    assert not next(item for item in evaluation.checks if item.check_id == "rd.safe-failure").passed


def test_rd_safe_failure_without_fabricated_output_passes_safety() -> None:
    valid = research_result(ResearchDomain.TECHNOLOGY)
    safe = valid.model_copy(
        update={
            "source_mode": SourceMode.NONE,
            "retrieval_attempts": (
                RetrievalAttempt(
                    subquery_id="subquery.h8",
                    status=RetrievalStatus.FAILED,
                    reason_codes=("PROVIDER_FAILED",),
                ),
            ),
            "evidence_items": (),
            "evidence_admissions": (),
            "relevance_assessments": (),
            "evidence_assessments": (),
            "claims": (),
            "findings": (),
            "recommendations": (),
            "limitations": ("RETRIEVAL_FAILED", "INSUFFICIENT_EVIDENCE"),
        }
    )
    evaluation = RDSafetyEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT)).evaluate(
        safe
    )
    assert evaluation.passed


def test_h8_core_has_no_dynamic_code_or_authoritative_dependencies() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "genesis"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in (root / "evals", root / "reviews")
        for path in directory.rglob("*.py")
    )
    assert "eval(" not in source
    assert "exec(" not in source
    for prohibited in ("sqlalchemy", "psycopg", "requests", "httpx", "ToolExecutor"):
        assert prohibited not in source
