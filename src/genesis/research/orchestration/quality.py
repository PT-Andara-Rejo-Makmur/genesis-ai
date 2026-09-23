"""Deterministic, explainable research evidence quality policy."""

from __future__ import annotations

from collections.abc import Mapping

from genesis.research.orchestration.models import (
    CLASSIFICATION_RANK,
    EvidenceQualityAssessment,
    EvidenceUsability,
    QualityTier,
    ResearchEvidenceItem,
)
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.runtime.context import DataClassification


class EvidenceQualityPolicy:
    """Assess provenance, freshness, and reliability without opaque model scoring."""

    def assess(
        self,
        item: ResearchEvidenceItem,
        execution_context: Mapping[str, object],
        *,
        historical_question: bool = False,
    ) -> EvidenceQualityAssessment:
        ref = item.evidence_ref
        freshness = self._freshness(ref)
        reliability = self._reliability(ref)
        identity_valid = all(
            ref.get(field) == execution_context.get(field)
            for field in ("tenant_id", "organization_id", "workspace_id")
        )
        required_provenance = all(
            ref.get(field)
            for field in (
                "evidence_id",
                "source_id",
                "source_version",
                "content_hash",
                "captured_at",
            )
        )
        scopes = set(ref.get("scope_refs", []))
        raw_active_scopes = execution_context.get("scope_refs", [])
        active_scopes = (
            set(raw_active_scopes)
            if isinstance(raw_active_scopes, (list, tuple, set, frozenset))
            else set()
        )
        classification = str(ref.get("data_classification", ""))
        active_classification = str(execution_context.get("data_classification", ""))
        classification_valid = (
            classification in CLASSIFICATION_RANK
            and active_classification in CLASSIFICATION_RANK
            and CLASSIFICATION_RANK[classification] <= CLASSIFICATION_RANK[active_classification]
        )
        if (
            not identity_valid
            or not required_provenance
            or not scopes
            or not scopes.issubset(active_scopes)
            or not classification_valid
            or ref.get("validation_status") != "VALID"
            or ref.get("instruction_authority") is not False
        ):
            return EvidenceQualityAssessment(
                evidence_id=item.evidence_id,
                tier=QualityTier.EXCLUDED,
                freshness=freshness,
                reliability=reliability,
                usability=EvidenceUsability.EXCLUDED,
                reason_codes=("PROVENANCE_OR_AUTHORITY_INVALID",),
                confidence_cap=0,
            )
        if freshness is FreshnessStatus.CURRENT:
            if reliability is SourceReliability.HIGH:
                return self._result(item, QualityTier.STRONG, EvidenceUsability.PRIMARY, 0.95)
            if reliability is SourceReliability.MEDIUM:
                return self._result(item, QualityTier.MODERATE, EvidenceUsability.SUPPORTING, 0.75)
            reason = (
                "CURRENT_LOW_RELIABILITY"
                if reliability is SourceReliability.LOW
                else "CURRENT_UNVERIFIED"
            )
            return EvidenceQualityAssessment(
                evidence_id=item.evidence_id,
                tier=QualityTier.WEAK,
                freshness=freshness,
                reliability=reliability,
                usability=EvidenceUsability.WEAK,
                reason_codes=(reason,),
                confidence_cap=0.4 if reliability is SourceReliability.LOW else 0.3,
            )
        if freshness is FreshnessStatus.STALE:
            usable = (
                EvidenceUsability.SUPPORTING
                if historical_question
                and reliability in {SourceReliability.HIGH, SourceReliability.MEDIUM}
                else EvidenceUsability.HISTORICAL_ONLY
            )
            return EvidenceQualityAssessment(
                evidence_id=item.evidence_id,
                tier=QualityTier.WEAK,
                freshness=freshness,
                reliability=reliability,
                usability=usable,
                reason_codes=("STALE_HISTORICAL_ONLY",),
                confidence_cap=0.5 if historical_question else 0.4,
            )
        return EvidenceQualityAssessment(
            evidence_id=item.evidence_id,
            tier=QualityTier.WEAK,
            freshness=freshness,
            reliability=reliability,
            usability=EvidenceUsability.WEAK,
            reason_codes=("FRESHNESS_UNKNOWN",),
            confidence_cap=0.35,
        )

    @staticmethod
    def _freshness(ref: Mapping[str, object]) -> FreshnessStatus:
        try:
            return FreshnessStatus(str(ref.get("freshness", "UNKNOWN")))
        except ValueError:
            return FreshnessStatus.UNKNOWN

    @staticmethod
    def _reliability(ref: Mapping[str, object]) -> SourceReliability:
        try:
            return SourceReliability(str(ref.get("reliability", "UNVERIFIED")))
        except ValueError:
            return SourceReliability.UNVERIFIED

    @staticmethod
    def _result(
        item: ResearchEvidenceItem,
        tier: QualityTier,
        usability: EvidenceUsability,
        cap: float,
    ) -> EvidenceQualityAssessment:
        return EvidenceQualityAssessment(
            evidence_id=item.evidence_id,
            tier=tier,
            freshness=FreshnessStatus.CURRENT,
            reliability=(
                SourceReliability.HIGH if tier is QualityTier.STRONG else SourceReliability.MEDIUM
            ),
            usability=usability,
            reason_codes=(f"CURRENT_{tier.value}",),
            confidence_cap=cap,
        )


def classification_allows_external(value: object) -> bool:
    return str(value) != DataClassification.RESTRICTED.value
