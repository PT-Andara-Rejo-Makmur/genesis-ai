"""Canonical, authority-bound admission for every research evidence ingestion path."""

from __future__ import annotations

from collections.abc import Mapping

from genesis.contracts import CanonicalContractCatalog
from genesis.research.orchestration.models import (
    CLASSIFICATION_RANK,
    EvidenceAdmissionAssessment,
    ResearchEvidenceItem,
)

EVIDENCE_REF_SCHEMA = "https://schemas.alos.dev/v1/evidence/evidence-ref.schema.json"


class ResearchEvidenceAdmissionPolicy:
    """Answer whether evidence may enter reasoning; it does not score quality."""

    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def admit(
        self,
        item: ResearchEvidenceItem,
        execution_context: Mapping[str, object],
    ) -> tuple[ResearchEvidenceItem | None, EvidenceAdmissionAssessment]:
        evidence_id = item.evidence_id or "unknown-evidence"
        try:
            canonical = self._contracts.validate(EVIDENCE_REF_SCHEMA, item.evidence_ref)
        except (TypeError, ValueError):
            return None, self._rejected(evidence_id, "CANONICAL_EVIDENCE_INVALID")

        evidence_id = str(canonical["evidence_id"])
        required_governance = (
            "tenant_id",
            "organization_id",
            "workspace_id",
            "scope_refs",
            "data_classification",
            "source_type",
            "freshness",
            "reliability",
            "instruction_authority",
            "validation_status",
        )
        if any(field not in canonical for field in required_governance):
            return None, self._rejected(evidence_id, "EVIDENCE_GOVERNANCE_METADATA_MISSING")
        if any(
            canonical[field] != execution_context.get(field)
            for field in ("tenant_id", "organization_id", "workspace_id")
        ):
            return None, self._rejected(evidence_id, "EVIDENCE_IDENTITY_MISMATCH")

        raw_scopes = execution_context.get("scope_refs", ())
        active_scopes = (
            set(raw_scopes) if isinstance(raw_scopes, (list, tuple, set, frozenset)) else set()
        )
        if not set(canonical["scope_refs"]).issubset(active_scopes):
            return None, self._rejected(evidence_id, "EVIDENCE_SCOPE_EXPANSION")

        evidence_classification = str(canonical["data_classification"])
        active_classification = str(execution_context.get("data_classification", ""))
        if (
            evidence_classification not in CLASSIFICATION_RANK
            or active_classification not in CLASSIFICATION_RANK
            or CLASSIFICATION_RANK[evidence_classification]
            > CLASSIFICATION_RANK[active_classification]
        ):
            return None, self._rejected(evidence_id, "EVIDENCE_CLASSIFICATION_EXPANSION")

        if canonical["validation_status"] != "VALID":
            return None, self._rejected(evidence_id, "EVIDENCE_NOT_VALID")
        if canonical["instruction_authority"] is not False:
            return None, self._rejected(evidence_id, "EVIDENCE_INSTRUCTION_AUTHORITY")
        if canonical["source_type"] == "EXTERNAL" and canonical.get("content_trust") != "UNTRUSTED":
            return None, self._rejected(evidence_id, "EXTERNAL_EVIDENCE_TRUST_INVALID")

        admitted = item.model_copy(update={"evidence_ref": canonical})
        return admitted, EvidenceAdmissionAssessment(
            evidence_id=evidence_id,
            admitted=True,
            reason_codes=("CANONICAL_EVIDENCE_ADMITTED",),
        )

    @staticmethod
    def _rejected(evidence_id: str, reason: str) -> EvidenceAdmissionAssessment:
        return EvidenceAdmissionAssessment(
            evidence_id=evidence_id,
            admitted=False,
            reason_codes=(reason,),
        )
