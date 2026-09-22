"""Canonical tool/model/result projections for the agentic loop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

from jsonschema import Draft202012Validator

from genesis.model_gateway.types import ModelResponse
from genesis.runtime.agentic.models import AgenticRuntimeState, RuntimeFailure, StopReason
from genesis.runtime.agentic.state import fail


def tool_request(
    request: dict[str, Any],
    tool_id: str,
    arguments: dict[str, Any],
    step_index: int,
) -> dict[str, Any]:
    canonical_arguments = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    seed = f"{request['run_id']}:{step_index}:{tool_id}:{canonical_arguments}".encode()
    digest = hashlib.sha256(seed).hexdigest()
    return {
        "tool_call_id": f"toolcall_{digest[:20]}",
        "run_id": request["run_id"],
        "tool_id": tool_id,
        "execution_context": request["execution_context"],
        "arguments": arguments,
        "idempotency_key": f"agentic-{digest}",
        "requested_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def validate_tool_result(
    request: dict[str, Any], result: dict[str, Any], state: AgenticRuntimeState
) -> None:
    expected = {
        "tool_call_id": request["tool_call_id"],
        "run_id": request["run_id"],
        "tool_id": request["tool_id"],
        "correlation_id": request["execution_context"]["correlation_id"],
    }
    mismatches = sorted(key for key, value in expected.items() if result.get(key) != value)
    if mismatches:
        raise fail(
            state,
            "TOOL_RESULT_IDENTITY_MISMATCH",
            "ToolResult identifiers do not match the canonical ToolRequest.",
            StopReason.TOOL_FAILED,
        )


def parse_output(response: ModelResponse, state: AgenticRuntimeState) -> Any:
    try:
        return json.loads(response.content)
    except json.JSONDecodeError as exc:
        raise fail(
            state,
            "MODEL_OUTPUT_INVALID_JSON",
            "Model output is not valid JSON.",
            StopReason.OUTPUT_INVALID,
            output_state="NEEDS_REVIEW",
        ) from exc


def validate_json_schema(schema: Mapping[str, Any], payload: Any, code: str) -> None:
    errors = sorted(
        Draft202012Validator(dict(schema)).iter_errors(payload),
        key=lambda item: list(item.path),
    )
    if errors:
        raise RuntimeFailure(code, "Runtime payload does not satisfy the Agent schema.")


def validate_json_schema_with_state(
    schema: Mapping[str, Any], payload: Any, code: str, state: AgenticRuntimeState
) -> None:
    try:
        validate_json_schema(schema, payload, code)
    except RuntimeFailure as exc:
        exc.state = state
        exc.stop_reason = StopReason.OUTPUT_INVALID
        exc.output_state = "NEEDS_REVIEW"
        raise


def terminal_result(
    *,
    request: dict[str, Any],
    started: datetime,
    started_clock: float,
    state: AgenticRuntimeState,
    status: str,
    output_state: str,
    output: Any,
    tool_results: Sequence[dict[str, Any]],
    evidence_refs: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    context = cast(dict[str, Any], request["execution_context"])
    return {
        "run_id": request["run_id"],
        "root_run_id": request["root_run_id"],
        **({"parent_run_id": request["parent_run_id"]} if request.get("parent_run_id") else {}),
        "correlation_id": context["correlation_id"],
        "agent_id": request["agent_id"],
        "agent_version": request["agent_version"],
        "capability_id": request["capability_id"],
        "status": status,
        "output_state": output_state,
        "output": output,
        "usage": usage(state, started_clock),
        "tool_results": list(tool_results),
        "evidence_refs": list(evidence_refs),
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def failure_result(
    request: dict[str, Any],
    started: datetime,
    started_clock: float,
    failure: RuntimeFailure,
    tool_results: Sequence[dict[str, Any]],
    state: AgenticRuntimeState | None,
) -> dict[str, Any]:
    context = cast(dict[str, Any], request["execution_context"])
    result: dict[str, Any] = {
        "run_id": request["run_id"],
        "root_run_id": request["root_run_id"],
        **({"parent_run_id": request["parent_run_id"]} if request.get("parent_run_id") else {}),
        "correlation_id": context["correlation_id"],
        "agent_id": request["agent_id"],
        "agent_version": request["agent_version"],
        "capability_id": request["capability_id"],
        "status": failure.run_status,
        "output_state": failure.output_state,
        "tool_results": list(tool_results),
        "evidence_refs": [],
        "error": {
            "code": failure.code,
            "message": failure.message,
            "correlation_id": context["correlation_id"],
            "retryable": failure.retryable,
            **(
                {"details": {"stop_reason": failure.stop_reason.value}}
                if failure.stop_reason is not None
                else {}
            ),
        },
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    if state is not None:
        result["usage"] = usage(state, started_clock)
    return result


def usage(state: AgenticRuntimeState, started_clock: float) -> dict[str, Any]:
    routes = tuple(dict.fromkeys(state.route_ids))
    return {
        **({"provider": routes[0], "model": routes[0]} if len(routes) == 1 else {}),
        "input_tokens": state.input_tokens,
        "output_tokens": state.output_tokens,
        "latency_milliseconds": max(0, int((monotonic() - started_clock) * 1000)),
        **({"estimated_cost": state.estimated_cost} if state.estimated_cost > 0 else {}),
    }
