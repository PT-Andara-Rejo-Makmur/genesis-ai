"""Retrieve governed context through the Backend ToolExecutor boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from genesis.contracts import CanonicalContractCatalog
from genesis.runtime.execution import BackendToolClient

CONTEXT_BUNDLE_SCHEMA = "https://schemas.alos.dev/v1/context/context-bundle.schema.json"


@dataclass(frozen=True, slots=True)
class ContextRetrievalError(Exception):
    code: str
    message: str
    correlation_id: str


class BackendContextProvider:
    """Build ToolRequest; never query source, evidence, or business persistence directly."""

    def __init__(
        self,
        *,
        tool_client: BackendToolClient,
        contracts: CanonicalContractCatalog,
    ) -> None:
        self._tool_client = tool_client
        self._contracts = contracts

    async def retrieve(
        self,
        *,
        run_id: str,
        query: str,
        execution_context: Mapping[str, Any],
        limit: int = 12,
        max_characters: int = 12_000,
    ) -> dict[str, Any]:
        correlation_id = str(execution_context["correlation_id"])
        digest = hashlib.sha256(
            f"{run_id}:{correlation_id}:{query}".encode()
        ).hexdigest()[:24]
        payload = {
            "tool_call_id": f"toolcall_{digest}",
            "run_id": run_id,
            "tool_id": "source.search_context",
            "execution_context": dict(execution_context),
            "arguments": {
                "query": query,
                "limit": limit,
                "max_characters": max_characters,
            },
        }
        result = await self._tool_client.execute(payload, correlation_id=correlation_id)
        if result["status"] != "SUCCESS":
            error = result.get("error", {})
            raise ContextRetrievalError(
                code=str(error.get("code", "CONTEXT_RETRIEVAL_FAILED")),
                message=str(error.get("message", "Backend context retrieval failed.")),
                correlation_id=correlation_id,
            )
        output = result.get("output")
        if not isinstance(output, Mapping):
            raise ContextRetrievalError(
                code="CONTEXT_RESPONSE_INVALID",
                message="Backend ToolResult output is not a ContextBundle object.",
                correlation_id=correlation_id,
            )
        validated = self._contracts.validate(CONTEXT_BUNDLE_SCHEMA, output)
        if validated["correlation_id"] != correlation_id:
            raise ContextRetrievalError(
                code="CONTEXT_CORRELATION_MISMATCH",
                message="ContextBundle correlation_id does not match the request.",
                correlation_id=correlation_id,
            )
        return validated
