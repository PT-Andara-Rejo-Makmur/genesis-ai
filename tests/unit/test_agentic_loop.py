from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from genesis.agents.definitions import AgentDefinition
from genesis.contracts import CanonicalContractCatalog
from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.runtime.agentic import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    AgentRuntimeEngine,
    ModelUsage,
    RuntimeAuthorization,
    StopReason,
    ToolCallIntent,
)

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


class QueuePlanner:
    def __init__(self, decisions: Sequence[AgenticDecision]) -> None:
        self.decisions = list(decisions)
        self.states: list[AgenticRuntimeState] = []

    async def next_action(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        del definition, request
        self.states.append(state)
        return self.decisions.pop(0)


class ObservationPlanner:
    async def next_action(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        del definition, request
        if not state.observations:
            return tool_decision("diagnostic.echo", {"sequence": 1})
        return finish({"summary": f"observed:{state.observations[0].output['value']}"})


class EndlessPlanner:
    async def next_action(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        del definition, request
        return tool_decision("diagnostic.echo", {"step": state.step_count})


class SlowPlanner:
    async def next_action(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        del definition, request, state
        await asyncio.sleep(2)
        return finish({"summary": "late"})


class InvalidPlanner:
    async def next_action(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
    ) -> Any:
        del definition, request, state
        return {"kind": "FINISH"}


class FakeGateway:
    def __init__(self, response: ModelResponse | Exception | None = None) -> None:
        self.response = response or ModelResponse(
            content=json.dumps({"summary": "model-finished"}),
            route_id="route.test",
            input_tokens=3,
            output_tokens=2,
            cost=0.1,
        )
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeToolClient:
    def __init__(self, statuses: Sequence[str] = ("SUCCESS",)) -> None:
        self.statuses = list(statuses)
        self.requests: list[dict[str, Any]] = []
        self.mutate: dict[str, Any] = {}

    async def execute(
        self, payload: dict[str, Any], *, correlation_id: str
    ) -> dict[str, Any]:
        self.requests.append(dict(payload))
        status = self.statuses.pop(0)
        result: dict[str, Any] = {
            "tool_call_id": payload["tool_call_id"],
            "run_id": payload["run_id"],
            "tool_id": payload["tool_id"],
            "correlation_id": correlation_id,
            "status": status,
            "completed_at": "2026-09-22T10:00:00Z",
        }
        if status in {"SUCCESS", "COMPLETED"}:
            result["output"] = {"value": len(self.requests)}
        else:
            result["error"] = {
                "code": f"BACKEND_{status}",
                "message": "governed tool failure",
                "correlation_id": correlation_id,
                "retryable": status in {"FAILED", "TIMEOUT"},
            }
        result.update(self.mutate)
        return result


class SequenceCancellation:
    def __init__(self, values: Sequence[bool]) -> None:
        self.values = list(values)
        self.calls = 0

    async def is_cancelled(self, run_id: str) -> bool:
        del run_id
        self.calls += 1
        return self.values.pop(0) if self.values else False


class TraceObserver:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def on_step_started(self, state: AgenticRuntimeState) -> None:
        self.events.append(("step", state.step_count))

    def on_tool_requested(self, tool_call_id: str, tool_id: str, step_index: int) -> None:
        self.events.append(("tool-request", (tool_call_id, tool_id, step_index)))

    def on_tool_result(self, tool_call_id: str, status: str, step_index: int) -> None:
        self.events.append(("tool-result", (tool_call_id, status, step_index)))

    def on_stop(self, reason: StopReason, state: AgenticRuntimeState) -> None:
        self.events.append(("stop", (reason, state.step_count)))


def definition(**changes: Any) -> AgentDefinition:
    value: dict[str, Any] = {
        "agent_id": "agent_h5_runtime_001",
        "agent_version": "1.0.0",
        "name": "H5 Runtime",
        "purpose": "Execute a bounded governed workflow.",
        "capability_ids": ("capability_h5_runtime",),
        "allowed_tool_ids": ("diagnostic.echo", "diagnostic.second"),
        "permission_refs": ("tools.diagnostic.execute",),
        "scope_refs": ("scope.h5",),
        "model_policy_ref": "policy.runtime-test",
        "input_schema": {
            "type": "object",
            "required": ["message"],
            "properties": {"message": {"type": "string"}},
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    value.update(changes)
    return AgentDefinition.model_validate(value)


def evidence_ref() -> dict[str, Any]:
    return {
        "tenant_id": "tenant_h5_001",
        "organization_id": "organization_h5_001",
        "workspace_id": "workspace_h5_001",
        "run_id": "run_origin_001",
        "correlation_id": "corr_origin_001",
        "scope_refs": ["scope.h5"],
        "evidence_id": "evidence_h5_001",
        "source_id": "source_h5_001",
        "uri": "urn:alos:evidence:h5:1",
        "captured_at": "2026-09-22T09:00:00Z",
        "retrieved_at": "2026-09-22T09:00:00Z",
        "content_hash": "sha256:" + "a" * 64,
        "source_version": "1.0.0",
        "anchor": "section:1",
        "excerpt": "Governed current evidence.",
        "data_classification": "INTERNAL",
        "source_type": "INTERNAL",
        "freshness": "CURRENT",
        "reliability": "HIGH",
        "content_trust": "GOVERNED",
        "instruction_authority": False,
        "validation_status": "VALID",
    }


def run_request(
    *,
    max_tokens: int = 100,
    max_cost: float | None = 2,
    max_steps: int = 5,
    max_tool_calls: int = 4,
    timeout_seconds: int = 5,
    requested_tool_ids: Sequence[str] = ("diagnostic.echo", "diagnostic.second"),
    with_evidence: bool = False,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "run_id": "run_h5_runtime_001",
        "root_run_id": "run_h5_runtime_001",
        "agent_id": "agent_h5_runtime_001",
        "agent_version": "1.0.0",
        "capability_id": "capability_h5_runtime",
        "execution_context": {
            "tenant_id": "tenant_h5_001",
            "organization_id": "organization_h5_001",
            "workspace_id": "workspace_h5_001",
            "actor_id": "actor_h5_001",
            "authority_context": {"role": "researcher", "authority_level": "REQUESTER"},
            "permission_refs": ["tools.diagnostic.execute"],
            "scope_refs": ["scope.h5"],
            "data_classification": "INTERNAL",
            "correlation_id": "corr_h5_runtime_001",
            "execution_budget": {
                "max_tokens": max_tokens,
                "max_cost": max_cost,
                "max_steps": max_steps,
                "max_tool_calls": max_tool_calls,
                "timeout_seconds": timeout_seconds,
            },
        },
        "input": {"message": "run bounded workflow"},
        "requested_tool_ids": list(requested_tool_ids),
        "execution_mode": "TEST",
    }
    if with_evidence:
        request["context_bundle"] = {
            "context_id": "context_h5_001",
            "tenant_id": "tenant_h5_001",
            "organization_id": "organization_h5_001",
            "workspace_id": "workspace_h5_001",
            "actor_id": "actor_h5_001",
            "correlation_id": "corr_h5_runtime_001",
            "goal": "Use current governed evidence.",
            "scope_refs": ["scope.h5"],
            "created_at": "2026-09-22T09:30:00Z",
            "items": [],
            "evidence_refs": [evidence_ref()],
        }
    return request


def authorization(*, tools: Sequence[str] = ("diagnostic.echo", "diagnostic.second")):
    return RuntimeAuthorization(
        run_id="run_h5_runtime_001",
        registry_digest="a" * 64,
        lifecycle_state="TEST_AUTHORIZED",
        allowed_tool_ids=tuple(tools),
    )


def tool_decision(tool_id: str, arguments: dict[str, Any]) -> AgenticDecision:
    return AgenticDecision(
        kind=AgenticActionKind.TOOL,
        tool_intent=ToolCallIntent(tool_id=tool_id, arguments=arguments),
    )


def finish(output: Any, **changes: Any) -> AgenticDecision:
    return AgenticDecision(kind=AgenticActionKind.FINISH, output=output, **changes)


def engine(
    planner: Any,
    *,
    gateway: FakeGateway | None = None,
    tool_client: FakeToolClient | None = None,
    cancellation: SequenceCancellation | None = None,
    observer: TraceObserver | None = None,
) -> tuple[AgentRuntimeEngine, FakeGateway, FakeToolClient]:
    model = gateway or FakeGateway()
    tools = tool_client or FakeToolClient(("SUCCESS", "SUCCESS", "SUCCESS"))
    return (
        AgentRuntimeEngine(
            contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
            planner=planner,
            model_gateway=model,
            tool_client=tools,
            cancellation_probe=cancellation,
            observer=observer,
        ),
        model,
        tools,
    )


@pytest.mark.asyncio
async def test_no_tool_success() -> None:
    runtime, gateway, tools = engine(QueuePlanner((finish({"summary": "done"}),)))
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["status"] == "COMPLETED"
    assert result["output_state"] == "AI_INFERRED"
    assert not gateway.requests
    assert not tools.requests


@pytest.mark.asyncio
async def test_one_tool_then_finish_and_observation_affects_action() -> None:
    trace = TraceObserver()
    runtime, _, tools = engine(ObservationPlanner(), observer=trace)
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["output"] == {"summary": "observed:1"}
    assert len(result["tool_results"]) == 1
    assert len(tools.requests) == 1
    assert trace.events[-1][0] == "stop"


@pytest.mark.asyncio
async def test_two_sequential_tools_then_finish() -> None:
    planner = QueuePlanner(
        (
            tool_decision("diagnostic.echo", {"sequence": 1}),
            tool_decision("diagnostic.second", {"sequence": 2}),
            finish({"summary": "two observations"}),
        )
    )
    runtime, _, tools = engine(planner)
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["status"] == "COMPLETED"
    assert len(result["tool_results"]) == 2
    assert planner.states[-1].observations[-1].output == {"value": 2}
    assert [item["tool_id"] for item in tools.requests] == [
        "diagnostic.echo",
        "diagnostic.second",
    ]


@pytest.mark.asyncio
async def test_max_steps_stops_endless_planner_without_unbounded_loop() -> None:
    runtime, _, tools = engine(EndlessPlanner())
    result = await runtime.run(
        definition(), run_request(max_steps=2, max_tool_calls=4), authorization()
    )
    assert result["error"]["code"] == "BUDGET_STEPS_EXCEEDED"
    assert result["error"]["details"]["stop_reason"] == "MAX_STEPS"
    assert len(tools.requests) == 2


@pytest.mark.asyncio
async def test_max_tool_calls_stops_before_extra_boundary_call() -> None:
    runtime, _, tools = engine(EndlessPlanner())
    result = await runtime.run(
        definition(), run_request(max_steps=4, max_tool_calls=1), authorization()
    )
    assert result["error"]["code"] == "BUDGET_TOOL_CALLS_EXCEEDED"
    assert len(tools.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_tools", "definition_tools", "backend_tools", "code"),
    [
        ((), ("diagnostic.echo",), ("diagnostic.echo",), "TOOL_NOT_REQUESTED"),
        (("diagnostic.echo",), ("diagnostic.second",), ("diagnostic.echo",), "TOOL_NOT_DEFINED"),
        (("diagnostic.echo",), ("diagnostic.echo",), (), "TOOL_NOT_AUTHORIZED"),
    ],
)
async def test_tool_must_be_in_three_way_authority_intersection(
    request_tools: tuple[str, ...],
    definition_tools: tuple[str, ...],
    backend_tools: tuple[str, ...],
    code: str,
) -> None:
    runtime, _, tools = engine(QueuePlanner((tool_decision("diagnostic.echo", {}),)))
    result = await runtime.run(
        definition(allowed_tool_ids=definition_tools),
        run_request(requested_tool_ids=request_tools),
        authorization(tools=backend_tools),
    )
    assert result["error"]["code"] == code
    assert not tools.requests


@pytest.mark.asyncio
async def test_tool_request_is_canonical_and_idempotency_is_deterministic() -> None:
    async def run_once() -> dict[str, Any]:
        runtime, _, tools = engine(
            QueuePlanner(
                (tool_decision("diagnostic.echo", {"b": 2, "a": 1}), finish({"summary": "ok"}))
            )
        )
        result = await runtime.run(definition(), run_request(), authorization())
        assert result["status"] == "COMPLETED"
        return tools.requests[0]

    first = await run_once()
    second = await run_once()
    assert first["idempotency_key"] == second["idempotency_key"]
    assert first["tool_call_id"] == second["tool_call_id"]
    assert first["execution_context"] == run_request()["execution_context"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ({"tool_call_id": "toolcall_wrong_001"}, "TOOL_RESULT_IDENTITY_MISMATCH"),
        ({"run_id": "run_wrong_001"}, "TOOL_RESULT_IDENTITY_MISMATCH"),
        ({"tool_id": "diagnostic.wrong"}, "TOOL_RESULT_IDENTITY_MISMATCH"),
        ({"correlation_id": "corr_wrong_001"}, "TOOL_RESULT_IDENTITY_MISMATCH"),
    ],
)
async def test_tool_result_identity_mismatch_is_blocked(
    mutation: dict[str, Any], code: str
) -> None:
    tools = FakeToolClient()
    tools.mutate = mutation
    runtime, _, _ = engine(QueuePlanner((tool_decision("diagnostic.echo", {}),)), tool_client=tools)
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["error"]["code"] == code


@pytest.mark.asyncio
async def test_malformed_tool_result_is_safe_and_not_retried() -> None:
    tools = FakeToolClient()
    tools.mutate = {"status": "UNKNOWN"}
    runtime, _, _ = engine(EndlessPlanner(), tool_client=tools)
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["error"]["code"] == "TOOL_RESULT_INVALID"
    assert len(tools.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code", "stop_reason"),
    [
        ("DENIED", "TOOL_DENIED", "TOOL_DENIED"),
        ("REJECTED", "TOOL_REJECTED", "TOOL_DENIED"),
        ("FAILED", "TOOL_FAILED", "TOOL_FAILED"),
        ("TIMEOUT", "TOOL_TIMEOUT", "TOOL_FAILED"),
    ],
)
async def test_tool_failure_statuses_stop_without_blind_retry(
    status: str, code: str, stop_reason: str
) -> None:
    tools = FakeToolClient((status, "SUCCESS"))
    runtime, _, _ = engine(EndlessPlanner(), tool_client=tools)
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["error"]["code"] == code
    assert result["error"]["details"]["stop_reason"] == stop_reason
    assert len(tools.requests) == 1


@pytest.mark.asyncio
async def test_model_gateway_failure_invalid_json_and_schema_fail_safely() -> None:
    cases = (
        (FakeGateway(RuntimeError("provider secret")), "MODEL_GATEWAY_FAILED"),
        (
            FakeGateway(
                ModelResponse(
                    content="not-json",
                    route_id="route.test",
                    input_tokens=1,
                    output_tokens=1,
                )
            ),
            "MODEL_OUTPUT_INVALID_JSON",
        ),
        (
            FakeGateway(
                ModelResponse(
                    content=json.dumps({"wrong": True}),
                    route_id="route.test",
                    input_tokens=1,
                    output_tokens=1,
                )
            ),
            "OUTPUT_SCHEMA_INVALID",
        ),
    )
    for gateway, expected in cases:
        planner = QueuePlanner(
            (
                AgenticDecision(
                    kind=AgenticActionKind.FINISH,
                    messages=({"role": "user", "content": "finish"},),
                ),
            )
        )
        runtime, _, _ = engine(planner, gateway=gateway)
        result = await runtime.run(definition(), run_request(), authorization())
        assert result["status"] == "FAILED"
        assert result["error"]["code"] == expected


@pytest.mark.asyncio
async def test_invalid_planner_structure_fails_safely() -> None:
    runtime, _, _ = engine(InvalidPlanner())
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["error"]["code"] == "PLANNER_OUTPUT_INVALID"


@pytest.mark.asyncio
async def test_cumulative_token_and_cost_budgets_are_enforced() -> None:
    token_planner = QueuePlanner(
        (
            tool_decision("diagnostic.echo", {}).model_copy(
                update={"planner_usage": ModelUsage(input_tokens=6, output_tokens=2)}
            ),
            finish({"summary": "too late"}).model_copy(
                update={"planner_usage": ModelUsage(input_tokens=3, output_tokens=1)}
            ),
        )
    )
    runtime, _, _ = engine(token_planner)
    token_result = await runtime.run(
        definition(), run_request(max_tokens=10), authorization()
    )
    assert token_result["error"]["code"] == "BUDGET_TOKENS_EXCEEDED"
    assert token_result["usage"]["input_tokens"] == 9
    assert token_result["usage"]["output_tokens"] == 3

    cost_planner = QueuePlanner(
        (
            finish({"summary": "over cost"}).model_copy(
                update={"planner_usage": ModelUsage(estimated_cost=2.1)}
            ),
        )
    )
    cost_runtime, _, _ = engine(cost_planner)
    cost_result = await cost_runtime.run(
        definition(), run_request(max_cost=2), authorization()
    )
    assert cost_result["error"]["code"] == "BUDGET_COST_EXCEEDED"


@pytest.mark.asyncio
async def test_remaining_token_budget_decreases_and_caps_model_request() -> None:
    planner = QueuePlanner(
        (
            tool_decision("diagnostic.echo", {}).model_copy(
                update={"planner_usage": ModelUsage(input_tokens=10, output_tokens=5)}
            ),
            AgenticDecision(
                kind=AgenticActionKind.FINISH,
                messages=({"role": "user", "content": "finish"},),
                planner_usage=ModelUsage(input_tokens=4, output_tokens=1),
            ),
        )
    )
    runtime, gateway, _ = engine(planner)
    result = await runtime.run(definition(), run_request(max_tokens=50), authorization())
    assert planner.states[0].remaining_tokens == 50
    assert planner.states[1].remaining_tokens == 35
    assert gateway.requests[0].requested_max_tokens == 30
    assert result["usage"]["input_tokens"] == 17
    assert result["usage"]["output_tokens"] == 8


@pytest.mark.asyncio
async def test_cancel_before_first_step_and_between_steps() -> None:
    before = SequenceCancellation((True,))
    runtime, gateway, tools = engine(
        QueuePlanner((finish({"summary": "never"}),)), cancellation=before
    )
    result = await runtime.run(definition(), run_request(), authorization())
    assert result["status"] == "CANCELLED"
    assert result["error"]["code"] == "RUNTIME_CANCELLED"
    assert not gateway.requests and not tools.requests

    between = SequenceCancellation((False, False, True))
    runtime2, gateway2, tools2 = engine(EndlessPlanner(), cancellation=between)
    result2 = await runtime2.run(definition(), run_request(), authorization())
    assert result2["status"] == "CANCELLED"
    assert len(tools2.requests) == 1
    assert not gateway2.requests


@pytest.mark.asyncio
async def test_whole_run_timeout_maps_to_canonical_timed_out() -> None:
    runtime, _, _ = engine(SlowPlanner())
    result = await runtime.run(
        definition(), run_request(timeout_seconds=1), authorization()
    )
    assert result["status"] == "TIMED_OUT"
    assert result["error"]["code"] == "RUNTIME_TIMEOUT"


@pytest.mark.asyncio
async def test_needs_info_and_approval_required_stop_without_tool() -> None:
    review_schema = {
        "type": "object",
        "required": ["summary"],
        "properties": {"summary": {"type": "string"}},
        "additionalProperties": False,
    }
    for kind in (AgenticActionKind.NEEDS_INFO, AgenticActionKind.APPROVAL_REQUIRED):
        planner = QueuePlanner(
            (AgenticDecision(kind=kind, output={"summary": kind.value}),)
        )
        runtime, _, tools = engine(planner)
        result = await runtime.run(
            definition(output_schema=review_schema), run_request(), authorization()
        )
        assert result["status"] == "COMPLETED"
        assert result["output_state"] == "NEEDS_REVIEW"
        assert not tools.requests


@pytest.mark.asyncio
async def test_agent_approval_required_stops_before_material_tool() -> None:
    planner = QueuePlanner((tool_decision("diagnostic.echo", {"material": True}),))
    runtime, _, tools = engine(planner)
    result = await runtime.run(
        definition(
            approval_required=True,
            output_schema={
                "type": "object",
                "required": ["status", "reason"],
                "properties": {
                    "status": {"const": "APPROVAL_REQUIRED"},
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
        run_request(),
        authorization(),
    )
    assert result["status"] == "COMPLETED"
    assert result["output_state"] == "NEEDS_REVIEW"
    assert not tools.requests


@pytest.mark.asyncio
async def test_evidence_is_real_selected_and_never_fabricated() -> None:
    valid = finish(
        {"summary": "evidence-backed"},
        evidence_ids=("evidence_h5_001",),
        requires_evidence=True,
    )
    runtime, _, _ = engine(QueuePlanner((valid,)))
    result = await runtime.run(
        definition(), run_request(with_evidence=True), authorization()
    )
    assert result["evidence_refs"][0]["evidence_id"] == "evidence_h5_001"
    assert result["correlation_id"] == "corr_h5_runtime_001"
    assert result["evidence_refs"][0]["correlation_id"] == "corr_origin_001"

    fake = finish(
        {"summary": "unsupported"}, evidence_ids=("evidence_fake_001",), requires_evidence=True
    )
    runtime2, _, _ = engine(QueuePlanner((fake,)))
    failed = await runtime2.run(definition(), run_request(with_evidence=True), authorization())
    assert failed["error"]["code"] == "EVIDENCE_INSUFFICIENT"
    assert failed["evidence_refs"] == []
