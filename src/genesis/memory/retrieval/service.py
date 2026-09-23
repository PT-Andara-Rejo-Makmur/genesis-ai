"""Fail-closed, deterministic memory filtering, deduplication, and ranking."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from genesis.memory.models import (
    ExcludedMemory,
    MemoryCandidate,
    MemoryQuery,
    MemoryRecordStatus,
    MemoryScore,
    MemorySelection,
    SelectedMemory,
    SuppressedDuplicate,
)
from genesis.memory.retrieval.ports import MemoryRetrievalPort
from genesis.research.models import FindingKind
from genesis.runtime.context.models import (
    DataClassification,
    EvidenceReference,
    ExecutionContextView,
    Freshness,
)

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
_RELIABILITY_RANK = {"UNVERIFIED": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
_TOKEN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


class MemoryRetrievalService:
    """Select memory without granting authority or relying on input ordering."""

    def __init__(self, provider: MemoryRetrievalPort) -> None:
        self._provider = provider

    async def retrieve(
        self,
        *,
        context: ExecutionContextView,
        query: MemoryQuery,
        active_scope_refs: Sequence[str],
        now: datetime | None = None,
    ) -> MemorySelection:
        candidates = await self._provider.retrieve_candidates(context=context, query=query)
        return self.select(
            candidates=candidates,
            context=context,
            query=query,
            active_scope_refs=active_scope_refs,
            now=now,
        )

    def select(
        self,
        *,
        candidates: Sequence[MemoryCandidate],
        context: ExecutionContextView,
        query: MemoryQuery,
        active_scope_refs: Sequence[str],
        now: datetime | None = None,
    ) -> MemorySelection:
        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        ordered = sorted(candidates, key=lambda item: item.memory_id)[: query.maximum_candidates]
        eligible: list[MemoryCandidate] = []
        excluded: list[ExcludedMemory] = []
        for candidate in ordered:
            reason = self._exclusion_reason(
                candidate,
                context=context,
                query=query,
                active_scope_refs=active_scope_refs,
                now=timestamp,
            )
            if reason is None:
                eligible.append(candidate)
            else:
                excluded.append(ExcludedMemory(memory_id=candidate.memory_id, reason_code=reason))

        winners, suppressed = self._deduplicate(eligible)
        scored = [
            SelectedMemory(
                candidate=item,
                score=self._score(item, query=query, now=timestamp),
                fingerprint=self.fingerprint(item),
            )
            for item in winners
        ]
        below_threshold = [item for item in scored if item.score.total < query.minimum_score]
        excluded.extend(
            ExcludedMemory(
                memory_id=item.candidate.memory_id,
                reason_code="RELEVANCE_BELOW_THRESHOLD",
            )
            for item in below_threshold
        )
        selected = tuple(
            sorted(
                (item for item in scored if item.score.total >= query.minimum_score),
                key=lambda item: (
                    -item.score.total,
                    -item.candidate.created_at.timestamp(),
                    item.candidate.memory_id,
                ),
            )[: query.maximum_selected]
        )
        selected_ids = {item.candidate.memory_id for item in selected}
        excluded.extend(
            ExcludedMemory(
                memory_id=item.candidate.memory_id,
                reason_code="SELECTION_LIMIT_REACHED",
            )
            for item in scored
            if item.score.total >= query.minimum_score
            and item.candidate.memory_id not in selected_ids
        )
        return MemorySelection(
            selected=selected,
            excluded=tuple(sorted(excluded, key=lambda item: (item.memory_id, item.reason_code))),
            suppressed_duplicates=tuple(
                sorted(suppressed, key=lambda item: (item.selected_memory_id, item.memory_id))
            ),
            processed_candidates=len(ordered),
        )

    @staticmethod
    def _exclusion_reason(
        candidate: MemoryCandidate,
        *,
        context: ExecutionContextView,
        query: MemoryQuery,
        active_scope_refs: Sequence[str],
        now: datetime,
    ) -> str | None:
        if candidate.tenant_id != context.tenant_id:
            return "TENANT_MISMATCH"
        if candidate.organization_id != context.organization_id:
            return "ORGANIZATION_MISMATCH"
        if candidate.workspace_id != context.workspace_id:
            return "WORKSPACE_MISMATCH"
        if not set(candidate.scope_refs).issubset(active_scope_refs):
            return "SCOPE_MISMATCH"
        if not set(candidate.scope_refs).issubset(context.scope_refs):
            return "SCOPE_MISMATCH"
        if (
            _CLASSIFICATION_RANK[candidate.data_classification]
            > _CLASSIFICATION_RANK[context.data_classification]
        ):
            return "CLASSIFICATION_EXCEEDS_AUTHORITY"
        if candidate.status is not MemoryRecordStatus.ACTIVE:
            return "MEMORY_NOT_ACTIVE"
        if candidate.expires_at is not None and candidate.expires_at <= now:
            return "MEMORY_EXPIRED"
        if candidate.freshness is Freshness.STALE:
            return "MEMORY_STALE"
        if candidate.freshness is Freshness.UNKNOWN:
            return "MEMORY_FRESHNESS_UNKNOWN"
        if not candidate.evidence_refs or not candidate.source_refs:
            return "LINEAGE_REQUIRED"
        evidence_reason = MemoryRetrievalService._evidence_exclusion_reason(candidate, context)
        if evidence_reason is not None:
            return evidence_reason
        if query.require_research_findings and candidate.finding_kind is not FindingKind.RESEARCH:
            return "RESEARCH_FINDING_REQUIRED"
        if query.requested_domains:
            if candidate.domain not in query.requested_domains:
                return "RESEARCH_DOMAIN_MISMATCH"
            if not query.allow_multi_domain and len(query.requested_domains) != 1:
                return "MULTI_DOMAIN_NOT_AUTHORIZED"
        return None

    @staticmethod
    def _evidence_exclusion_reason(
        candidate: MemoryCandidate,
        context: ExecutionContextView,
    ) -> str | None:
        for evidence in candidate.evidence_refs:
            if (
                evidence.tenant_id != context.tenant_id
                or evidence.organization_id != context.organization_id
                or evidence.workspace_id != context.workspace_id
            ):
                return "EVIDENCE_IDENTITY_MISMATCH"
            if not set(evidence.scope_refs).issubset(candidate.scope_refs):
                return "EVIDENCE_SCOPE_MISMATCH"
            if not set(evidence.scope_refs).issubset(context.scope_refs):
                return "EVIDENCE_SCOPE_MISMATCH"
            if evidence.data_classification is not candidate.data_classification:
                return "EVIDENCE_CLASSIFICATION_MISMATCH"
            if evidence.validation_status != "VALID":
                return "EVIDENCE_INVALID"
            if evidence.freshness != Freshness.CURRENT.value:
                return "EVIDENCE_NOT_CURRENT"
            if candidate.originating_run_id is not None and (
                evidence.run_id != candidate.originating_run_id
                or evidence.correlation_id != candidate.originating_correlation_id
            ):
                return "ORIGIN_LINEAGE_MISMATCH"
        if set(candidate.source_refs) != {
            evidence.source_id for evidence in candidate.evidence_refs
        }:
            return "SOURCE_LINEAGE_MISMATCH"
        return None

    @staticmethod
    def fingerprint(candidate: MemoryCandidate) -> str:
        content = " ".join(candidate.content.casefold().split())
        lineage = ",".join(
            sorted(f"{item.source_id}:{item.content_hash}" for item in candidate.evidence_refs)
        )
        payload = "|".join(
            (
                content,
                candidate.domain.value if candidate.domain else "",
                candidate.finding_kind.value if candidate.finding_kind else "",
                ",".join(sorted(candidate.source_refs)),
                lineage,
            )
        )
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"

    @staticmethod
    def _deduplicate(
        candidates: Sequence[MemoryCandidate],
    ) -> tuple[list[MemoryCandidate], list[SuppressedDuplicate]]:
        groups: dict[str, list[MemoryCandidate]] = {}
        for candidate in candidates:
            groups.setdefault(MemoryRetrievalService.fingerprint(candidate), []).append(candidate)
        winners: list[MemoryCandidate] = []
        suppressed: list[SuppressedDuplicate] = []
        for fingerprint in sorted(groups):
            group = groups[fingerprint]
            winner = sorted(
                group,
                key=lambda item: (
                    -MemoryRetrievalService._evidence_strength(item.evidence_refs),
                    -item.created_at.timestamp(),
                    item.memory_id,
                ),
            )[0]
            winners.append(winner)
            suppressed.extend(
                SuppressedDuplicate(
                    memory_id=item.memory_id,
                    selected_memory_id=winner.memory_id,
                    fingerprint=fingerprint,
                )
                for item in group
                if item.memory_id != winner.memory_id
            )
        return winners, suppressed

    @staticmethod
    def _evidence_strength(evidence_refs: Sequence[EvidenceReference]) -> int:
        return sum(_RELIABILITY_RANK[item.reliability] for item in evidence_refs)

    @staticmethod
    def _score(candidate: MemoryCandidate, *, query: MemoryQuery, now: datetime) -> MemoryScore:
        goal_tokens = set(_TOKEN.findall(query.goal.casefold()))
        goal_tokens.update(
            token
            for value in query.capability_context
            for token in _TOKEN.findall(value.casefold())
        )
        content_tokens = set(_TOKEN.findall(candidate.content.casefold()))
        lexical = min(len(goal_tokens.intersection(content_tokens)) * 2, 20)
        domain = 8 if candidate.domain in query.requested_domains else 0
        explicit = 20 if candidate.memory_id in query.requested_memory_refs else 0
        source = 4 * len(set(candidate.source_refs).intersection(query.requested_source_refs))
        evidence = min(MemoryRetrievalService._evidence_strength(candidate.evidence_refs), 9)
        age = now - candidate.created_at.astimezone(UTC)
        recency = 3 if age <= timedelta(days=30) else 1 if age <= timedelta(days=90) else 0
        components = {
            "LEXICAL_OVERLAP": lexical,
            "DOMAIN_MATCH": domain,
            "EXPLICIT_MEMORY_REFERENCE": explicit,
            "SOURCE_MATCH": source,
            "VALIDATED_EVIDENCE": evidence,
            "RECENT_MEMORY": recency,
        }
        return MemoryScore(
            total=sum(components.values()),
            lexical_overlap=lexical,
            domain_match=domain,
            explicit_reference=explicit,
            source_match=source,
            evidence_strength=evidence,
            recency=recency,
            rule_ids=tuple(key for key, value in components.items() if value > 0),
        )
