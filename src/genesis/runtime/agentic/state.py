"""State construction, evidence selection, and cumulative budget accounting."""

from __future__ import annotations

import json
from typing import Any, cast

from genesis.model_gateway.types import ModelResponse
from genesis.runtime.agentic.models import (
    AgenticDecision,
    AgenticRuntimeState,
    ModelUsage,
    RuntimeFailure,
    StopReason,
)
from genesis.runtime.agentic.stopping import StoppingPolicy
from genesis.runtime.limits import ExecutionBudget

_CLASSIFICATION_RANK = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}


def fail(
    state: AgenticRuntimeState,
    code: str,
    message: str,
    reason: StopReason,
    *,
    retryable: bool = False,
    output_state: str | None = None,
    run_status: str | None = None,
) -> RuntimeFailure:
    projection = StoppingPolicy().project(reason)
    return RuntimeFailure(
        code,
        message,
        retryable=retryable,
        output_state=cast(Any, output_state or projection.output_state),
        run_status=cast(Any, run_status or projection.status),
        stop_reason=reason,
        state=state,
    )


def required_limit(value: int | None, name: str) -> int:
    if value is None:
        raise RuntimeFailure("BUDGET_REQUIRED", f"{name} is required for agentic execution.")
    return value


def initial_state(request: dict[str, Any], budget: ExecutionBudget) -> AgenticRuntimeState:
    context_bundle = cast(dict[str, Any], request.get("context_bundle") or {})
    goal = str(context_bundle.get("goal") or json.dumps(request["input"], sort_keys=True))
    evidence_ids = tuple(known_evidence(request))
    return AgenticRuntimeState(
        run_id=str(request["run_id"]),
        root_run_id=str(request["root_run_id"]),
        parent_run_id=str(request["parent_run_id"]) if request.get("parent_run_id") else None,
        correlation_id=str(request["execution_context"]["correlation_id"]),
        goal=goal,
        input=cast(dict[str, Any], request["input"]),
        known_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        max_tokens=required_limit(budget.max_tokens, "max_tokens"),
        max_cost=budget.max_cost,
    )


def known_evidence(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bundle = cast(dict[str, Any], request.get("context_bundle") or {})
    context = cast(dict[str, Any], request["execution_context"])
    known: dict[str, dict[str, Any]] = {}
    for raw in bundle.get("evidence_refs", []):
        if not isinstance(raw, dict):
            continue
        if raw.get("validation_status") != "VALID" or raw.get("freshness") != "CURRENT":
            continue
        if any(
            raw.get(field) not in {None, context[field]}
            for field in ("tenant_id", "organization_id", "workspace_id")
        ):
            continue
        if not set(raw.get("scope_refs", [])).issubset(context.get("scope_refs", [])):
            continue
        raw_classification = raw.get("data_classification")
        active_classification = context.get("data_classification")
        evidence_classification = (
            _CLASSIFICATION_RANK.get(raw_classification)
            if isinstance(raw_classification, str)
            else None
        )
        context_classification = (
            _CLASSIFICATION_RANK.get(active_classification)
            if isinstance(active_classification, str)
            else None
        )
        if (
            evidence_classification is None
            or context_classification is None
            or evidence_classification > context_classification
        ):
            continue
        if raw.get("instruction_authority") is not False:
            continue
        if raw.get("source_type") == "EXTERNAL" and raw.get("content_trust") != "UNTRUSTED":
            continue
        known[str(raw["evidence_id"])] = raw
    return known


def select_evidence(
    decision: AgenticDecision,
    known: dict[str, dict[str, Any]],
    state: AgenticRuntimeState,
) -> list[dict[str, Any]]:
    missing = sorted(set(decision.evidence_ids).difference(known))
    if missing or (decision.requires_evidence and not decision.evidence_ids):
        raise fail(
            state,
            "EVIDENCE_INSUFFICIENT",
            "The final decision requires evidence that is not available to the runtime.",
            StopReason.EVIDENCE_INSUFFICIENT,
            output_state="NEEDS_REVIEW",
        )
    return [known[item] for item in decision.evidence_ids]


def account_planner_usage(
    state: AgenticRuntimeState, usage: ModelUsage | None
) -> AgenticRuntimeState:
    if usage is None:
        return state
    return state.model_copy(
        update={
            "input_tokens": state.input_tokens + usage.input_tokens,
            "output_tokens": state.output_tokens + usage.output_tokens,
            "estimated_cost": state.estimated_cost + (usage.estimated_cost or 0),
            "route_ids": (
                (*state.route_ids, usage.route_id)
                if usage.route_id is not None
                else state.route_ids
            ),
        }
    )


def account_model_response(
    state: AgenticRuntimeState, response: ModelResponse
) -> AgenticRuntimeState:
    return state.model_copy(
        update={
            "input_tokens": state.input_tokens + response.input_tokens,
            "output_tokens": state.output_tokens + response.output_tokens,
            "estimated_cost": state.estimated_cost + (response.cost or 0),
            "route_ids": (*state.route_ids, response.route_id),
        }
    )


def enforce_cumulative_budget(state: AgenticRuntimeState) -> None:
    if state.consumed_tokens + state.reserved_child_tokens > state.max_tokens:
        raise fail(
            state,
            "BUDGET_TOKENS_EXCEEDED",
            "Parent model usage and child reservations exceeded the token budget.",
            StopReason.BUDGET_EXHAUSTED,
        )
    if (
        state.max_cost is not None
        and state.estimated_cost + state.reserved_child_cost > state.max_cost
    ):
        raise fail(
            state,
            "BUDGET_COST_EXCEEDED",
            "Parent model usage and child reservations exceeded the cost budget.",
            StopReason.BUDGET_EXHAUSTED,
        )
