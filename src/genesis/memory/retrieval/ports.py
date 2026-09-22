"""Framework-neutral retrieval boundary for already-authorized memory candidates."""

from collections.abc import Sequence
from typing import Protocol

from genesis.memory.models import MemoryCandidate, MemoryQuery
from genesis.runtime.context.models import ExecutionContextView


class MemoryRetrievalPort(Protocol):
    async def retrieve_candidates(
        self,
        *,
        context: ExecutionContextView,
        query: MemoryQuery,
    ) -> Sequence[MemoryCandidate]: ...
