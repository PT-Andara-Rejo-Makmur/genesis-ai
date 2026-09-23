"""Backend delegation boundary port; GENESIS provides no persistence adapter."""

from typing import Any, Protocol

from genesis.orchestration.delegation.models import DelegationIntent


class DelegationBoundaryClient(Protocol):
    async def submit(self, intent: DelegationIntent, *, correlation_id: str) -> dict[str, Any]: ...
