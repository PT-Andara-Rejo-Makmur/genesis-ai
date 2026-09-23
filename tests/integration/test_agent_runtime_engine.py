import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from genesis.agents.definitions import AgentDefinition
from genesis.contracts import CanonicalContractCatalog
from genesis.model_gateway import GovernedModelGateway, ModelRequest, ModelResponse
from genesis.model_gateway.budget import ExecutionBudgetGuard
from genesis.model_gateway.policy import StaticModelPolicy
from genesis.model_gateway.routing import StaticModelRouter
from genesis.runtime.agentic import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    AgentRuntimeEngine,
    RuntimeAuthorization,
    ToolCallIntent,
)
from genesis.runtime.execution import BackendToolClient, ToolBoundaryContracts

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


class DiagnosticPlanner:
    async def next_action(
        self,
        _definition: AgentDefinition,
        _request: dict[str, object],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        if not state.observations:
            return AgenticDecision(
                kind=AgenticActionKind.TOOL,
                tool_intent=ToolCallIntent(
                    tool_id="diagnostic.echo",
                    arguments={"message": "runtime split"},
                ),
            )
        return AgenticDecision(
            kind=AgenticActionKind.FINISH,
            messages=({"role": "user", "content": "Run governed diagnostic"},),
        )


class DeterministicProvider:
    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        assert "governed_tool_results" in request.messages[-1]["content"]
        return ModelResponse(
            content=json.dumps({"summary": "governed runtime complete"}),
            route_id=route_id,
            input_tokens=14,
            output_tokens=6,
            cost=0,
        )


def definition() -> AgentDefinition:
    return AgentDefinition(
        agent_id="agent_runtime_diagnostic",
        agent_version="1.0.0",
        name="Runtime Diagnostic",
        purpose="Verify generic governed runtime execution.",
        capability_ids=("capability_runtime_diagnostic",),
        tool_ids=("diagnostic.echo",),
        permission_refs=("tools.diagnostic.execute",),
        scope_refs=("scope.diagnostic",),
        model_policy_ref="policy.runtime-test",
        input_schema={
            "type": "object",
            "required": ["message"],
            "properties": {"message": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    )


def run_request(*, max_tool_calls: int = 1) -> dict[str, object]:
    return {
        "run_id": "run_runtime_split_001",
        "root_run_id": "run_runtime_split_001",
        "agent_id": "agent_runtime_diagnostic",
        "agent_version": "1.0.0",
        "capability_id": "capability_runtime_diagnostic",
        "execution_context": {
            "tenant_id": "tenant_diagnostic_001",
            "organization_id": "org_diagnostic_001",
            "workspace_id": "workspace_diagnostic_001",
            "actor_id": "actor_diagnostic_001",
            "authority_context": {
                "role": "diagnostic_runner",
                "authority_level": "SYSTEM",
            },
            "permission_refs": ["tools.diagnostic.execute"],
            "scope_refs": ["scope.diagnostic"],
            "data_classification": "INTERNAL",
            "correlation_id": "corr_runtime_split_001",
            "execution_budget": {
                "max_tokens": 200,
                "max_steps": 2,
                "max_tool_calls": max_tool_calls,
                "timeout_seconds": 5,
            },
        },
        "input": {"message": "runtime split"},
        "requested_tool_ids": ["diagnostic.echo"],
        "execution_mode": "TEST",
    }


def authorization(*, lifecycle: str = "TEST_AUTHORIZED") -> RuntimeAuthorization:
    return RuntimeAuthorization(
        run_id="run_runtime_split_001",
        registry_digest="a" * 64,
        lifecycle_state=lifecycle,  # type: ignore[arg-type]
        allowed_tool_ids=("diagnostic.echo",),
    )


async def make_engine(
    handler: httpx.MockTransport,
) -> tuple[AgentRuntimeEngine, httpx.AsyncClient]:
    http = httpx.AsyncClient(transport=handler, base_url="http://backend.test")
    tool_client = BackendToolClient(
        base_url="http://backend.test",
        internal_token=SecretStr("test-only-token"),
        contracts=ToolBoundaryContracts(CONTRACTS_ROOT),
        client=http,
    )
    gateway = GovernedModelGateway(
        policy=StaticModelPolicy(frozenset({"policy.runtime-test"})),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            routes={"route.test": DeterministicProvider()},
            policy_routes={"policy.runtime-test": "route.test"},
        ),
    )
    return (
        AgentRuntimeEngine(
            contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
            planner=DiagnosticPlanner(),
            model_gateway=gateway,
            tool_client=tool_client,
        ),
        http,
    )


@pytest.mark.asyncio
async def test_runtime_end_to_end_uses_backend_tool_boundary() -> None:
    seen_request: dict[str, object] = {}

    def backend_handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = json.loads(request.content)
        assert request.url.path == "/internal/v1/tool-requests"
        assert request.headers["X-Correlation-ID"] == "corr_runtime_split_001"
        return httpx.Response(
            200,
            json={
                "tool_call_id": seen_request["tool_call_id"],
                "run_id": seen_request["run_id"],
                "tool_id": "diagnostic.echo",
                "correlation_id": "corr_runtime_split_001",
                "status": "SUCCESS",
                "output": {
                    "echo": {"message": "runtime split"},
                    "label": "NON-PRODUCTION TEST TOOL",
                },
                "completed_at": "2026-09-17T10:00:01Z",
            },
        )

    engine, http = await make_engine(httpx.MockTransport(backend_handler))
    try:
        result = await engine.run(definition(), run_request(), authorization())
    finally:
        await http.aclose()

    assert seen_request["tool_id"] == "diagnostic.echo"
    assert seen_request["execution_context"] == run_request()["execution_context"]
    assert result["status"] == "COMPLETED"
    assert result["tool_results"][0]["status"] == "SUCCESS"
    assert result["correlation_id"] == "corr_runtime_split_001"


@pytest.mark.asyncio
async def test_runtime_rejects_plan_that_exceeds_tool_budget_before_http() -> None:
    calls = 0

    def backend_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    engine, http = await make_engine(httpx.MockTransport(backend_handler))
    try:
        result = await engine.run(
            definition(),
            run_request(max_tool_calls=0),
            authorization(),
        )
    finally:
        await http.aclose()

    assert calls == 0
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "BUDGET_TOOL_CALLS_EXCEEDED"


@pytest.mark.asyncio
async def test_runtime_requires_backend_lifecycle_authorization() -> None:
    engine, http = await make_engine(httpx.MockTransport(lambda _request: httpx.Response(500)))
    bad_authorization = authorization().model_copy(update={"run_id": "run_other_001"})
    try:
        result = await engine.run(definition(), run_request(), bad_authorization)
    finally:
        await http.aclose()

    assert result["status"] == "FAILED"
    assert result["output_state"] == "BLOCKED"
    assert result["error"]["code"] == "RUN_AUTHORIZATION_MISMATCH"
