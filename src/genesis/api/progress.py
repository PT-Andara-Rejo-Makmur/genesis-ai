"""Forward public operational events at the authenticated Backend HTTP boundary."""

import asyncio
from typing import Any

import httpx
from pydantic import SecretStr

from genesis.runtime.agentic.models import AgenticRuntimeState, StopReason


class BackendProgressObserver:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: SecretStr,
        run_id: str,
        correlation_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=2)
        self._owns_client = client is None
        self._url = f"{base_url.rstrip('/')}/internal/v1/agent-runs/{run_id}/progress"
        self._headers = {
            "Authorization": f"Bearer {internal_token.get_secret_value()}",
            "X-Correlation-ID": correlation_id,
        }
        self._correlation_id = correlation_id
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=64)
        self._sequence = 0
        self._sender = asyncio.create_task(self._send())

    def _event(self, kind: str) -> None:
        # Bounds are technical transport limits, never business authority thresholds.
        if self._sequence >= 240 or self._events.full():
            return
        self._sequence += 1
        self._events.put_nowait(
            {"event_key": str(self._sequence), "kind": kind, "correlation_id": self._correlation_id}
        )

    def on_step_started(self, state: AgenticRuntimeState) -> None:
        del state
        self._event("ANALYZING")

    def on_tool_requested(self, tool_call_id: str, tool_id: str, step_index: int) -> None:
        del tool_call_id, tool_id, step_index
        self._event("RETRIEVING")

    def on_tool_result(self, tool_call_id: str, status: str, step_index: int) -> None:
        del tool_call_id, status, step_index
        self._event("ANALYZING")

    def on_stop(self, reason: StopReason, state: AgenticRuntimeState) -> None:
        del reason, state
        # Only Backend may claim completion after validating the result.
        self._event("PREPARING")

    async def _send(self) -> None:
        while (event := await self._events.get()) is not None:
            try:
                await self._client.post(self._url, headers=self._headers, json=event, timeout=2)
            except httpx.HTTPError:
                # Diagnostics never decide whether an otherwise governed run succeeds.
                pass

    async def close(self) -> None:
        try:
            async with asyncio.timeout(3):
                await self._events.put(None)
                await self._sender
        except TimeoutError:
            self._sender.cancel()
            await asyncio.gather(self._sender, return_exceptions=True)
        finally:
            if self._owns_client:
                await self._client.aclose()
