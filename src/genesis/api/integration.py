"""Composition for authenticated Backend-to-GENESIS runtime boundaries."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import SecretStr

from genesis.agents.definitions import AgentDefinition
from genesis.config import Settings
from genesis.contracts import CanonicalContractCatalog
from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.runtime.agentic import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    AgentRuntimeEngine,
    ModelUsage,
    RuntimeAuthorization,
    ToolCallIntent,
)
from genesis.runtime.execution import BackendToolClient, ToolBoundaryContracts


class DeterministicIntegrationPlanner:
    """Bounded test adapter; it never bypasses ModelGateway in normal execution."""

    async def next_action(
        self,
        _definition: AgentDefinition,
        request: Mapping[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        usage = ModelUsage(
            input_tokens=2,
            output_tokens=1,
            estimated_cost=0,
            route_id="deterministic.integration",
        )
        requested = tuple(str(item) for item in request.get("requested_tool_ids", ()))
        if requested and not state.observations:
            raw_input = request.get("input", {})
            arguments = dict(raw_input) if isinstance(raw_input, Mapping) else {}
            return AgenticDecision(
                kind=AgenticActionKind.TOOL,
                tool_intent=ToolCallIntent(tool_id=requested[0], arguments=arguments),
                planner_usage=usage,
            )
        raw_input = request.get("input", {})
        if (
            state.observations
            and isinstance(raw_input, Mapping)
            and raw_input.get("wait_for_cancellation") is True
        ):
            await asyncio.sleep(1)
        return AgenticDecision(
            kind=AgenticActionKind.FINISH,
            output={
                "summary": "Governed deterministic runtime completed.",
                "tool_status": state.observations[-1].status
                if state.observations
                else "NOT_REQUESTED",
            },
            planner_usage=usage,
        )


class DisabledModelGateway:
    async def complete(self, _request: ModelRequest) -> ModelResponse:
        raise RuntimeError("Deterministic integration output must not invoke a model provider.")


class DeterministicResearchGateway:
    """Deterministic TEST provider that remains behind the ModelGateway boundary."""

    def __init__(self, *, evidence_id: str, domain: str) -> None:
        self._evidence_id = evidence_id
        self._domain = domain
        self._suffix = hashlib.sha256(evidence_id.encode()).hexdigest()[:20]

    async def complete(self, _request: ModelRequest) -> ModelResponse:
        content = {
            "findings": [
                {
                    "finding_id": f"finding.integration.{self._suffix}",
                    "finding_type": "RESEARCH",
                    "domain": self._domain,
                    "title": "Deterministic integration evidence",
                    "statement": "Backend-authorized evidence was analyzed deterministically.",
                    "severity": "LOW",
                    "confidence": 1.0,
                    "evidence_ids": [self._evidence_id],
                    "limitations": ["Deterministic integration provider only."],
                }
            ],
            "recommendations": [
                {
                    "recommendation_id": f"recommendation.integration.{self._suffix}",
                    "summary": "Keep the authorized evidence under human review.",
                    "recommended_action": "Create a draft backlog candidate for human review.",
                    "confidence": 1.0,
                    "finding_ids": [f"finding.integration.{self._suffix}"],
                    "evidence_ids": [self._evidence_id],
                    "limitations": ["No production model provider was used."],
                    "backlog_candidate": True,
                }
            ],
            "limitations": ["Deterministic integration provider only."],
        }
        return ModelResponse(
            content=json.dumps(content),
            route_id="deterministic.integration.research",
            input_tokens=5,
            output_tokens=10,
            cost=0,
        )


class BackendCancellationProbe:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: SecretStr,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = internal_token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=5)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def is_cancelled(self, run_id: str) -> bool:
        headers: dict[str, str] = {}
        token = self._token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = await self._client.get(
            f"/internal/v1/agent-runs/{run_id}/cancellation",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        return isinstance(payload, dict) and payload.get("cancellation_state") in {
            "REQUESTED",
            "CANCELLED",
        }


async def run_deterministic_invocation(
    *,
    settings: Settings,
    contracts: CanonicalContractCatalog,
    definition: AgentDefinition,
    run_request: dict[str, Any],
    authorization: RuntimeAuthorization,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Execute the explicit TEST route through the real Backend ToolExecutor boundary."""

    if settings.ALOS_CONTRACTS_PATH is None:
        raise ValueError("ALOS_CONTRACTS_PATH is required for runtime integration")
    tool_client = BackendToolClient(
        base_url=settings.ALOS_BACKEND_BASE_URL,
        internal_token=settings.ALOS_INTERNAL_TOKEN,
        contracts=ToolBoundaryContracts(settings.ALOS_CONTRACTS_PATH),
        client=http_client,
    )
    cancellation = BackendCancellationProbe(
        base_url=settings.ALOS_BACKEND_BASE_URL,
        internal_token=settings.ALOS_INTERNAL_TOKEN,
        client=http_client,
    )
    try:
        engine = AgentRuntimeEngine(
            contracts=contracts,
            planner=DeterministicIntegrationPlanner(),
            model_gateway=DisabledModelGateway(),
            tool_client=tool_client,
            cancellation_probe=cancellation,
        )
        return await engine.run(definition, run_request, authorization)
    finally:
        await cancellation.close()
        await tool_client.close()
