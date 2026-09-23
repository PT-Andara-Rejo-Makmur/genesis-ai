"""Independent deterministic assurance evaluation of research output."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from genesis.contracts import CanonicalContractCatalog
from genesis.research.domains import domain_profile
from genesis.research.models import ResearchDomain
from genesis.research.orchestration import (
    ClaimKind,
    EvidenceUsability,
    QualityTier,
    ResearchOrchestrationResult,
    RetrievalStatus,
    SourceMode,
)
from genesis.research.sources import FreshnessStatus, SourceReliability

EVIDENCE_REF_SCHEMA = "https://schemas.alos.dev/v1/evidence/evidence-ref.schema.json"
_AUTHORITY_WORDING = re.compile(
    r"\b(approve|approved|activate|release|execute|purchase|acquire|sell|grant permission)\b",
    re.IGNORECASE,
)
_DOMAIN_TERMS: dict[ResearchDomain, frozenset[str]] = {
    ResearchDomain.TECHNOLOGY: frozenset(
        {"benchmark", "proof", "security", "compatibility", "cost", "technical", "adoption"}
    ),
    ResearchDomain.PROPERTY_BUSINESS: frozenset(
        {"scenario", "pricing", "package", "unit", "economics", "commercial", "validation"}
    ),
    ResearchDomain.MANAGEMENT: frozenset(
        {"sop", "kpi", "control", "governance", "process", "pilot", "management"}
    ),
    ResearchDomain.PROPERTY_MARKET: frozenset(
        {"market", "region", "comparable", "site", "sensitivity", "due", "diligence"}
    ),
}


class RDSafetyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check_id: str
    passed: bool
    material: bool
    reason_codes: tuple[str, ...] = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


class RDSafetyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    domain: ResearchDomain
    passed: bool
    checks: tuple[RDSafetyCheck, ...]
    limitations: tuple[str, ...]


class RDSafetyEvaluator:
    """One evaluator for every R&D domain; profiles only configure semantic hints."""

    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def evaluate(self, result: ResearchOrchestrationResult) -> RDSafetyEvaluation:
        evidence = {item.evidence_id: item for item in result.evidence_items}
        canonical_ids: set[str] = set()
        invalid_ids: set[str] = set()
        external_invalid: set[str] = set()
        for evidence_id, item in evidence.items():
            try:
                canonical = self._contracts.validate(EVIDENCE_REF_SCHEMA, item.evidence_ref)
            except (TypeError, ValueError):
                invalid_ids.add(evidence_id)
                continue
            required_lineage = {
                "tenant_id",
                "organization_id",
                "workspace_id",
                "scope_refs",
                "evidence_id",
                "source_id",
                "source_version",
                "content_hash",
                "data_classification",
                "source_type",
                "freshness",
                "reliability",
                "instruction_authority",
                "validation_status",
            }
            if not required_lineage.issubset(canonical):
                invalid_ids.add(evidence_id)
                continue
            result_identity = {
                key: result.canonical_result.get(key)
                for key in ("tenant_id", "organization_id", "workspace_id")
                if result.canonical_result.get(key) is not None
            }
            if any(canonical.get(key) != value for key, value in result_identity.items()):
                invalid_ids.add(evidence_id)
                continue
            if canonical.get("validation_status") != "VALID":
                invalid_ids.add(evidence_id)
                continue
            canonical_ids.add(evidence_id)
            if canonical.get("source_type") == "EXTERNAL" and (
                canonical.get("content_trust") != "UNTRUSTED"
                or canonical.get("instruction_authority") is not False
            ):
                external_invalid.add(evidence_id)

        facts = tuple(item for item in result.claims if item.kind is ClaimKind.FACT)
        material_fact_ids = {evidence_id for item in facts for evidence_id in item.evidence_ids}
        finding_evidence = {
            evidence_id for item in result.findings for evidence_id in item.evidence_ids
        }
        recommendation_evidence = {
            evidence_id for item in result.recommendations for evidence_id in item.evidence_ids
        }
        known_findings = {item.finding_id for item in result.findings}
        unknown_finding_refs = {
            finding_id
            for item in result.recommendations
            for finding_id in item.finding_ids
            if finding_id not in known_findings
        }
        known_fact_ids = {item.claim_id for item in facts}
        known_assumption_ids = {item.claim_id for item in result.assumptions}
        known_conflict_ids = {item.conflict_id for item in result.conflicts}
        unknown_analysis_refs = {
            reference
            for item in result.recommendations
            for reference in (
                *(claim_id for claim_id in item.fact_claim_ids if claim_id not in known_fact_ids),
                *(
                    assumption_id
                    for assumption_id in item.assumption_ids
                    if assumption_id not in known_assumption_ids
                ),
                *(
                    conflict_id
                    for conflict_id in item.conflict_ids
                    if conflict_id not in known_conflict_ids
                ),
            )
        }
        unknown_analysis_refs.update(
            claim_id
            for item in result.findings
            for claim_id in item.fact_claim_ids
            if claim_id not in known_fact_ids
        )
        unknown_citations = (
            material_fact_ids | finding_evidence | recommendation_evidence
        ) - canonical_ids
        external_evidence = {
            evidence_id
            for evidence_id, item in evidence.items()
            if item.evidence_ref.get("source_type") == "EXTERNAL" and evidence_id in canonical_ids
        }
        external_adequate = result.source_mode not in {
            SourceMode.EXTERNAL_ONLY,
            SourceMode.MIXED,
        } or bool(external_evidence)

        stale_ids = {
            item.evidence_id
            for item in result.evidence_assessments
            if item.freshness in {FreshnessStatus.STALE, FreshnessStatus.UNKNOWN}
        }
        high_confidence_stale = any(
            item.confidence > 0.5 and set(item.evidence_ids) and set(item.evidence_ids) <= stale_ids
            for item in result.findings
        )
        stale_disclosed = not stale_ids or any(
            token
            in " ".join(
                (
                    *result.limitations,
                    *(value for item in result.findings for value in item.limitations),
                )
            ).upper()
            for token in ("STALE", "HISTORICAL", "FRESHNESS")
        )
        conflict_ids = {item.conflict_id for item in result.conflicts if item.unresolved}
        surfaced_conflicts = {
            conflict_id for item in result.findings for conflict_id in item.conflict_ids
        } | {conflict_id for item in result.recommendations for conflict_id in item.conflict_ids}
        hidden_conflicts = conflict_ids - surfaced_conflicts

        assumption_ids = {item.claim_id for item in result.assumptions}
        fact_ids = {item.claim_id for item in facts}
        assumption_as_fact = bool(assumption_ids & fact_ids)
        failed_attempts = tuple(
            item for item in result.retrieval_attempts if item.status is not RetrievalStatus.SUCCESS
        )
        failure_visible = not failed_attempts or any(
            code in " ".join(result.limitations).upper()
            for code in ("FAILED", "TIMEOUT", "DENIED", "NO_RESULT", "RETRIEVAL")
        )

        quality_by_evidence = {item.evidence_id: item for item in result.evidence_assessments}
        material_evidence_ids = material_fact_ids | finding_evidence | recommendation_evidence
        source_quality_failures: set[str] = set()
        for evidence_id in material_evidence_ids:
            quality = quality_by_evidence.get(evidence_id)
            if quality is None or quality.usability is EvidenceUsability.EXCLUDED:
                source_quality_failures.add(evidence_id)
                continue
            if quality.tier not in {QualityTier.STRONG, QualityTier.MODERATE}:
                source_quality_failures.add(evidence_id)
                continue
            if quality.reliability not in {SourceReliability.HIGH, SourceReliability.MEDIUM}:
                source_quality_failures.add(evidence_id)
                continue
            if quality.usability not in {
                EvidenceUsability.PRIMARY,
                EvidenceUsability.SUPPORTING,
            }:
                source_quality_failures.add(evidence_id)

        confidence_violations: set[str] = set()
        for finding in result.findings:
            caps = [
                quality_by_evidence[evidence_id].confidence_cap
                for evidence_id in finding.evidence_ids
                if evidence_id in quality_by_evidence
            ]
            if not caps or finding.confidence > min(caps):
                confidence_violations.add(finding.finding_id)
        for recommendation in result.recommendations:
            caps = [
                quality_by_evidence[evidence_id].confidence_cap
                for evidence_id in recommendation.evidence_ids
                if evidence_id in quality_by_evidence
            ]
            qualitative_cap = (
                0.5 if recommendation.conflict_ids or recommendation.assumption_ids else 1.0
            )
            if not caps or recommendation.confidence > min((*caps, qualitative_cap)):
                confidence_violations.add(recommendation.recommendation_id)

        recommendation_authority = any(
            _AUTHORITY_WORDING.search(item.proposed_action) for item in result.recommendations
        )
        recommendation_substantive = all(
            self._domain_relevant(result.plan.domain, item.proposed_action)
            and item.requires_human_review
            and bool(item.limitations)
            for item in result.recommendations
        )
        if not result.recommendations:
            recommendation_substantive = bool(result.limitations)
        recommendation_quality = (
            recommendation_substantive
            and not recommendation_authority
            and not unknown_finding_refs
            and not unknown_analysis_refs
            and not unknown_citations
            and not source_quality_failures
            and not confidence_violations
        )

        profile = domain_profile(result.plan.domain)
        checks = (
            self._check(
                "rd.canonical-lineage", not invalid_ids, "CANONICAL_LINEAGE_INVALID", invalid_ids
            ),
            self._check(
                "rd.citation-complete",
                not unknown_citations,
                "UNKNOWN_OR_MISSING_CITATION",
                unknown_citations,
            ),
            self._check(
                "rd.fact-evidence",
                all(item.evidence_ids for item in facts),
                "MATERIAL_FACT_WITHOUT_EVIDENCE",
            ),
            self._check(
                "rd.finding-evidence",
                all(item.evidence_ids for item in result.findings),
                "MATERIAL_FINDING_WITHOUT_EVIDENCE",
            ),
            self._check(
                "rd.recommendation-links",
                not unknown_finding_refs and not unknown_analysis_refs,
                "UNKNOWN_RECOMMENDATION_FINDING",
                unknown_finding_refs | unknown_analysis_refs,
            ),
            self._check(
                "rd.external-trust",
                not external_invalid,
                "EXTERNAL_TRUST_INVALID",
                external_invalid,
            ),
            self._check(
                "rd.external-evidence",
                external_adequate,
                "EXTERNAL_RESEARCH_WITHOUT_CANONICAL_EVIDENCE",
            ),
            self._check(
                "rd.freshness",
                not high_confidence_stale and stale_disclosed,
                "STALE_ONLY_HIGH_CONFIDENCE",
            ),
            self._check(
                "rd.source-quality",
                not source_quality_failures and not confidence_violations,
                "MATERIAL_SOURCE_QUALITY_INADEQUATE",
                source_quality_failures | confidence_violations,
            ),
            self._check("rd.conflicts", not hidden_conflicts, "UNRESOLVED_CONFLICT_HIDDEN"),
            self._check("rd.assumptions", not assumption_as_fact, "ASSUMPTION_PRESENTED_AS_FACT"),
            self._check("rd.safe-failure", failure_visible, "FAILED_RETRIEVAL_NOT_DISCLOSED"),
            self._check(
                "rd.advisory-only",
                not recommendation_authority,
                "RECOMMENDATION_AUTHORITY_SEMANTICS",
            ),
            self._check(
                "rd.recommendation-quality",
                recommendation_quality,
                "RECOMMENDATION_QUALITY_INADEQUATE",
                confidence_violations,
            ),
            self._check(
                "rd.domain-quality",
                recommendation_substantive,
                f"{profile.domain.value}_RECOMMENDATION_NOT_SUBSTANTIVE",
            ),
        )
        return RDSafetyEvaluation(
            domain=result.plan.domain,
            passed=all(item.passed for item in checks if item.material),
            checks=checks,
            limitations=tuple(dict.fromkeys(result.limitations)),
        )

    @staticmethod
    def _domain_relevant(domain: ResearchDomain, action: str) -> bool:
        words = set(re.findall(r"[a-z0-9]+", action.lower()))
        return bool(words & _DOMAIN_TERMS[domain]) and len(words) >= 4

    @staticmethod
    def _check(
        check_id: str,
        passed: bool,
        reason_code: str,
        evidence_ids: set[str] | None = None,
    ) -> RDSafetyCheck:
        return RDSafetyCheck(
            check_id=check_id,
            passed=passed,
            material=True,
            reason_codes=(("CHECK_PASSED",) if passed else (reason_code,)),
            evidence_ids=tuple(sorted(evidence_ids or ())),
        )
