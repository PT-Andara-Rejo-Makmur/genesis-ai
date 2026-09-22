"""Generic H7 duplicate, corroboration, and unresolved conflict intelligence."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from genesis.research.orchestration.models import (
    ClaimAssessment,
    ClaimKind,
    ConflictAssessment,
    ConflictType,
    CorroborationAssessment,
    DuplicateAssessment,
    EvidenceQualityAssessment,
)
from genesis.research.sources import FreshnessStatus


class ClaimComparisonIntelligence:
    def compare(
        self,
        claims: tuple[ClaimAssessment, ...],
        assessments: tuple[EvidenceQualityAssessment, ...],
    ) -> tuple[
        tuple[DuplicateAssessment, ...],
        tuple[CorroborationAssessment, ...],
        tuple[ConflictAssessment, ...],
    ]:
        quality = {item.evidence_id: item for item in assessments}
        facts = tuple(item for item in claims if item.kind is ClaimKind.FACT)
        by_topic: dict[str, list[ClaimAssessment]] = defaultdict(list)
        for claim in facts:
            by_topic[claim.normalized_topic].append(claim)
        duplicates: list[DuplicateAssessment] = []
        corroborations: list[CorroborationAssessment] = []
        conflicts: list[ConflictAssessment] = []
        for topic, grouped in sorted(by_topic.items()):
            by_statement: dict[str, list[ClaimAssessment]] = defaultdict(list)
            for claim in grouped:
                by_statement[self._normalize(claim.statement)].append(claim)
            for equivalent in by_statement.values():
                if len(equivalent) < 2:
                    continue
                evidence_ids = tuple(
                    dict.fromkeys(
                        evidence_id
                        for claim in equivalent
                        for evidence_id in claim.evidence_ids
                    )
                )
                by_lineage: dict[
                    tuple[tuple[str, ...], tuple[str, ...]], list[ClaimAssessment]
                ] = defaultdict(list)
                for claim in equivalent:
                    by_lineage[(claim.source_ids, claim.source_versions)].append(claim)
                for same_lineage in by_lineage.values():
                    if len(same_lineage) < 2:
                        continue
                    duplicates.append(
                        DuplicateAssessment(
                            claim_ids=tuple(item.claim_id for item in same_lineage),
                            evidence_ids=tuple(
                                dict.fromkeys(
                                    evidence_id
                                    for claim in same_lineage
                                    for evidence_id in claim.evidence_ids
                                )
                            ),
                        )
                    )
                source_ids = tuple(
                    dict.fromkeys(
                        source_id
                        for claim in equivalent
                        for source_id in claim.source_ids
                    )
                )
                if len(source_ids) >= 2:
                    corroborations.append(
                        CorroborationAssessment(
                            topic=topic,
                            claim_ids=tuple(item.claim_id for item in equivalent),
                            source_ids=source_ids,
                            evidence_ids=evidence_ids,
                        )
                    )
            if len(by_statement) <= 1:
                continue
            competing = tuple(grouped)
            evidence_ids = tuple(
                dict.fromkeys(
                    evidence_id for claim in competing for evidence_id in claim.evidence_ids
                )
            )
            source_ids = tuple(
                dict.fromkeys(source_id for claim in competing for source_id in claim.source_ids)
            )
            versions = tuple(
                dict.fromkeys(
                    version for claim in competing for version in claim.source_versions
                )
            )
            freshness = {
                quality[evidence_id].freshness
                for evidence_id in evidence_ids
                if evidence_id in quality
            }
            if len(source_ids) == 1 and len(versions) > 1:
                conflict_type = ConflictType.SOURCE_VERSION
            elif {
                FreshnessStatus.CURRENT,
                FreshnessStatus.STALE,
            }.issubset(freshness):
                conflict_type = ConflictType.CURRENT_VS_STALE
            else:
                conflict_type = ConflictType.CLAIM_CONTRADICTION
            conflicts.append(
                ConflictAssessment(
                    conflict_id=self._identifier(topic, competing),
                    topic=topic,
                    competing_claim_ids=tuple(item.claim_id for item in competing),
                    evidence_ids=evidence_ids,
                    source_ids=source_ids,
                    source_versions=versions,
                    conflict_type=conflict_type,
                    limitations=("UNRESOLVED_SOURCE_CONFLICT",),
                )
            )
        return tuple(duplicates), tuple(corroborations), tuple(conflicts)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _identifier(topic: str, claims: tuple[ClaimAssessment, ...]) -> str:
        seed = topic + ":" + ":".join(sorted(item.claim_id for item in claims))
        return "conflict_" + hashlib.sha256(seed.encode()).hexdigest()[:20]
