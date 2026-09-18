"""GENESIS client for the authoritative Backend ToolExecutor boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from genesis.runtime.execution.contracts import ToolBoundaryContracts, ToolContractError


@dataclass(frozen=True, slots=True)
class BackendToolClientError(Exception):
    code: str
    message: str
    correlation_id: str
    retryable: bool
    status_code: int | None = None


class BackendToolClient:
    """Send ToolRequest to Backend; never load or execute a tool adapter locally."""

    def __init__(
        self,
        *,
        base_url: str,
        internal_token: SecretStr,
        contracts: ToolBoundaryContracts,
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = internal_token
        self._contracts = contracts
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout_seconds)
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        payload: Mapping[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]:
        self._contracts.validate_request(payload)
        context = payload["execution_context"]
        assert isinstance(context, Mapping)
        if context["correlation_id"] != correlation_id:
            raise ToolContractError(
                contract="ToolRequest",
                path="execution_context.correlation_id",
                reason="Transport and ToolRequest correlation identifiers must match.",
            )

        headers = {"X-Correlation-ID": correlation_id}
        token = self._token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._client.post(
                "/internal/v1/tool-requests",
                headers=headers,
                json=dict(payload),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BackendToolClientError(
                code="BACKEND_TOOL_TIMEOUT",
                message="ALOS Backend did not respond before the client timeout.",
                correlation_id=correlation_id,
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise BackendToolClientError(
                code="BACKEND_TOOL_HTTP_ERROR",
                message="ALOS Backend rejected the ToolRequest boundary call.",
                correlation_id=correlation_id,
                retryable=exc.response.status_code >= 500,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise BackendToolClientError(
                code="BACKEND_TOOL_UNAVAILABLE",
                message="ALOS Backend ToolExecutor boundary is unavailable.",
                correlation_id=correlation_id,
                retryable=True,
            ) from exc

        try:
            document = response.json()
        except ValueError as exc:
            raise BackendToolClientError(
                code="BACKEND_TOOL_INVALID_RESPONSE",
                message="ALOS Backend returned invalid JSON.",
                correlation_id=correlation_id,
                retryable=False,
                status_code=response.status_code,
            ) from exc
        if not isinstance(document, dict):
            raise BackendToolClientError(
                code="BACKEND_TOOL_INVALID_RESPONSE",
                message="ToolResult must be a JSON object.",
                correlation_id=correlation_id,
                retryable=False,
                status_code=response.status_code,
            )
        self._contracts.validate_result(document)
        if document["correlation_id"] != correlation_id:
            raise BackendToolClientError(
                code="BACKEND_TOOL_CORRELATION_MISMATCH",
                message="ToolResult correlation_id does not match ToolRequest.",
                correlation_id=correlation_id,
                retryable=False,
                status_code=response.status_code,
            )
        return document
