"""Deterministic and explainable H7 evidence relevance policy."""

from __future__ import annotations

import json
import re

from genesis.research.domains import domain_profile
from genesis.research.orchestration.models import (
    EvidenceNeed,
    EvidenceRelevance,
    EvidenceRelevanceAssessment,
    ResearchEvidenceItem,
    ResearchSubquery,
)

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "about",
    "adalah",
    "and",
    "atau",
    "dalam",
    "dengan",
    "evidence",
    "for",
    "from",
    "is",
    "pada",
    "required",
    "the",
    "untuk",
    "what",
    "yang",
}
_NEED_HINTS: dict[EvidenceNeed, set[str]] = {
    EvidenceNeed.CURRENT_STATE: {"current", "latest", "present", "status", "demand"},
    EvidenceNeed.COMPARABLE: {"benchmark", "comparable", "comparison", "peer"},
    EvidenceNeed.RISK: {"risk", "security", "constraint", "exposure"},
    EvidenceNeed.COST: {"cost", "price", "pricing", "budget", "economics"},
    EvidenceNeed.GOVERNANCE: {"governance", "policy", "sop", "control", "compliance"},
    EvidenceNeed.HISTORICAL: {"historical", "history", "prior", "trend"},
}


class EvidenceRelevancePolicy:
    """Classify relevance without granting authority or changing lineage."""

    def assess(
        self,
        item: ResearchEvidenceItem,
        subquery: ResearchSubquery,
    ) -> EvidenceRelevanceAssessment:
        if item.subquery_ids:
            if subquery.subquery_id in item.subquery_ids:
                return self._result(item, subquery, EvidenceRelevance.EXACT, 1.0, "EXPLICIT_MATCH")
            return self._result(
                item,
                subquery,
                EvidenceRelevance.IRRELEVANT,
                0,
                "EXPLICIT_MISMATCH",
            )

        question_tokens = self._tokens(subquery.question)
        ref = item.evidence_ref
        metadata = " ".join(
            str(ref.get(field, ""))
            for field in ("source_id", "anchor", "excerpt", "uri")
        )
        metadata += " " + json.dumps(ref.get("metadata", {}), sort_keys=True, default=str)
        evidence_tokens = self._tokens(f"{item.content} {metadata} {item.memory_ref or ''}")
        overlap = question_tokens.intersection(evidence_tokens)
        ratio = len(overlap) / max(1, len(question_tokens))
        need_overlap = _NEED_HINTS[subquery.evidence_need].intersection(evidence_tokens)
        profile_tokens = self._tokens(
            " ".join(domain_profile(subquery.domain).expected_evidence)
        )
        domain_overlap = question_tokens.intersection(profile_tokens).intersection(
            evidence_tokens
        )

        if len(overlap) >= 2 and (ratio >= 0.2 or need_overlap or domain_overlap):
            score = min(0.9, 0.45 + ratio + 0.05 * len(need_overlap | domain_overlap))
            return self._result(
                item,
                subquery,
                EvidenceRelevance.RELEVANT,
                score,
                "LEXICAL_AND_DOMAIN_RELEVANCE",
            )
        if overlap and (need_overlap or domain_overlap):
            return self._result(
                item,
                subquery,
                EvidenceRelevance.WEAK,
                min(0.49, 0.2 + ratio),
                "LIMITED_CONTEXT_OVERLAP",
            )
        return self._result(
            item,
            subquery,
            EvidenceRelevance.IRRELEVANT,
            0,
            "NO_MEANINGFUL_OVERLAP",
        )

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token
            for token in _TOKEN.findall(value.casefold())
            if len(token) >= 3 and token not in _STOP_WORDS
        }

    @staticmethod
    def _result(
        item: ResearchEvidenceItem,
        subquery: ResearchSubquery,
        relevance: EvidenceRelevance,
        score: float,
        reason: str,
    ) -> EvidenceRelevanceAssessment:
        return EvidenceRelevanceAssessment(
            evidence_id=item.evidence_id,
            subquery_id=subquery.subquery_id,
            relevance=relevance,
            reason_codes=(reason,),
            score=score,
        )
