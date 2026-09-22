"""Project selected historical memory into bounded ContextManager input."""

from genesis.memory.models import SelectedMemory
from genesis.runtime.context.models import (
    ContextPriority,
    ContextSegment,
    ContextSource,
    ContextTrust,
)


class MemoryContextFactory:
    def create(self, selected: SelectedMemory) -> ContextSegment:
        candidate = selected.candidate
        evidence = sorted(candidate.evidence_refs, key=lambda item: item.evidence_id)
        primary = evidence[0]
        trust = (
            ContextTrust.UNTRUSTED
            if any(item.source_type == "EXTERNAL" for item in evidence)
            else ContextTrust.GOVERNED
        )
        return ContextSegment(
            segment_id=f"memory_{candidate.memory_id}",
            key=f"historical-memory-{candidate.memory_id}",
            content=candidate.content,
            priority=ContextPriority.RELEVANT_MEMORY,
            source=ContextSource.MEMORY,
            trust=trust,
            freshness=candidate.freshness,
            data_classification=candidate.data_classification,
            scope_refs=candidate.scope_refs,
            evidence=primary,
            lineage_evidence_refs=tuple(evidence),
            memory_ref=candidate.memory_id,
        )
