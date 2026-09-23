"""Deterministic H7 findings, recommendations, and canonical projection."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from genesis.contracts import CanonicalContractCatalog
from genesis.research.models import ResearchDomain
from genesis.research.orchestration.models import (
    ClaimAssessment,
    ClaimKind,
    ConflictAssessment,
    CorroborationAssessment,
    EvidenceQualityAssessment,
    EvidenceUsability,
    ResearchEvidenceItem,
    ResearchFindingAnalysis,
    ResearchRecommendationAnalysis,
)

RESEARCH_RESULT_SCHEMA = "https://schemas.alos.dev/v1/research/research-result.schema.json"


class FindingRecommendationBuilder:
    """Produce proposals only; this component has no approval or execution operation."""

    def build(
        self,
        *,
        domain: ResearchDomain,
        claims: tuple[ClaimAssessment, ...],
        conflicts: tuple[ConflictAssessment, ...],
        corroborations: tuple[CorroborationAssessment, ...],
        assessments: tuple[EvidenceQualityAssessment, ...],
    ) -> tuple[
        tuple[ResearchFindingAnalysis, ...],
        tuple[ResearchRecommendationAnalysis, ...],
    ]:
        """Compatibility helper; recommendation synthesis is ModelGateway-only."""
        findings = self.build_findings(
            domain=domain,
            claims=claims,
            conflicts=conflicts,
            corroborations=corroborations,
            assessments=assessments,
        )
        return findings, ()

    def build_findings(
        self,
        *,
        domain: ResearchDomain,
        claims: tuple[ClaimAssessment, ...],
        conflicts: tuple[ConflictAssessment, ...],
        corroborations: tuple[CorroborationAssessment, ...],
        assessments: tuple[EvidenceQualityAssessment, ...],
    ) -> tuple[ResearchFindingAnalysis, ...]:
        quality = {item.evidence_id: item for item in assessments}
        conflict_by_claim: dict[str, list[str]] = {}
        for conflict in conflicts:
            for claim_id in conflict.competing_claim_ids:
                conflict_by_claim.setdefault(claim_id, []).append(conflict.conflict_id)
        corroborated = {
            claim_id for item in corroborations for claim_id in item.claim_ids
        }
        findings: list[ResearchFindingAnalysis] = []
        for claim in claims:
            if claim.kind is not ClaimKind.FACT or not claim.evidence_ids:
                continue
            if any(
                quality[evidence_id].usability is EvidenceUsability.EXCLUDED
                for evidence_id in claim.evidence_ids
            ):
                continue
            conflict_ids = tuple(sorted(conflict_by_claim.get(claim.claim_id, ())))
            confidence = claim.confidence
            if claim.claim_id in corroborated:
                confidence = min(0.95, confidence + 0.05)
            limitations: list[str] = []
            if conflict_ids:
                confidence = min(confidence, 0.5)
                limitations.append("UNRESOLVED_CONFLICT")
            if all(
                quality[evidence_id].usability
                in {EvidenceUsability.HISTORICAL_ONLY, EvidenceUsability.WEAK}
                for evidence_id in claim.evidence_ids
            ):
                confidence = min(confidence, 0.4)
                limitations.append("NO_STRONG_CURRENT_SUPPORT")
            quality_reasons = tuple(
                dict.fromkeys(
                    reason
                    for evidence_id in claim.evidence_ids
                    for reason in quality[evidence_id].reason_codes
                )
            )
            findings.append(
                ResearchFindingAnalysis(
                    finding_id=self._identifier("finding", claim.claim_id),
                    domain=domain,
                    statement=claim.statement,
                    fact_claim_ids=(claim.claim_id,),
                    conflict_ids=conflict_ids,
                    assumption_ids=(),
                    evidence_ids=claim.evidence_ids,
                    confidence=confidence,
                    quality_reasons=quality_reasons,
                    limitations=tuple(limitations),
                )
            )
        return tuple(findings)

    @staticmethod
    def _identifier(prefix: str, seed: str) -> str:
        return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:20]}"


class CanonicalResearchProjector:
    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def project(
        self,
        *,
        request: Mapping[str, Any],
        findings: tuple[ResearchFindingAnalysis, ...],
        recommendations: tuple[ResearchRecommendationAnalysis, ...],
        evidence_items: tuple[ResearchEvidenceItem, ...],
        limitations: tuple[str, ...],
    ) -> dict[str, Any]:
        context = request["execution_context"]
        evidence = {item.evidence_id: item.evidence_ref for item in evidence_items}
        canonical_findings = [
            {
                "finding_id": item.finding_id,
                "finding_type": "RESEARCH",
                "domain": item.domain.value,
                "statement": item.statement,
                "confidence": item.confidence,
                "output_state": "AI_INFERRED",
                "evidence_refs": [evidence[evidence_id] for evidence_id in item.evidence_ids],
                "limitations": list(item.limitations),
            }
            for item in findings
        ]
        canonical_recommendations = [
            {
                "recommendation_id": item.recommendation_id,
                "summary": "Human-reviewed R&D recommendation proposal.",
                "recommended_action": item.proposed_action,
                "confidence": item.confidence,
                "author_type": "AI",
                "finding_ids": list(item.finding_ids),
                "evidence_refs": [evidence[evidence_id] for evidence_id in item.evidence_ids],
                "limitations": list(item.limitations),
                "backlog_candidate": True,
            }
            for item in recommendations
        ]
        result: dict[str, Any] = {
            "research_id": request["research_id"],
            "run_id": request["run_id"],
            "tenant_id": context["tenant_id"],
            "organization_id": context["organization_id"],
            "workspace_id": context["workspace_id"],
            "correlation_id": request["correlation_id"],
            "output_state": "NEEDS_REVIEW",
            "findings": canonical_findings,
            "recommendations": canonical_recommendations,
            "limitations": list(dict.fromkeys((*limitations, "HUMAN_REVIEW_REQUIRED"))),
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        if evidence:
            result["evidence_bundle"] = {
                "bundle_id": self._identifier(
                    "bundle", f"{request['research_id']}:{request['correlation_id']}"
                ),
                "tenant_id": context["tenant_id"],
                "organization_id": context["organization_id"],
                "workspace_id": context["workspace_id"],
                "run_id": request["run_id"],
                "correlation_id": request["correlation_id"],
                "scope_refs": list(context["scope_refs"]),
                "evidence_refs": list(evidence.values()),
            }
        return self._contracts.validate(RESEARCH_RESULT_SCHEMA, result)

    @staticmethod
    def _identifier(prefix: str, seed: str) -> str:
        return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:20]}"
