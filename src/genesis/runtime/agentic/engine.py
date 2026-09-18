"""Generic runtime split from MVP-1 without framework or authority coupling."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

from jsonschema import Draft202012Validator

from genesis.agents.definitions import AgentDefinition
from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.runtime.agentic.models import (
    RuntimeAuthorization,
    RuntimeFailure,
    RuntimeRequestRejected,
)
from genesis.runtime.agentic.protocols import RuntimePlanner, ToolBoundaryClient
from genesis.runtime.limits import ExecutionBudget

AGENT_RUN_REQUEST_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-run-request.schema.json"
AGENT_RUN_RESULT_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-run-result.schema.json"


class AgentRuntimeEngine:
    """Consume Backend-authorized context and execute reasoning through governed ports."""

    def __init__(
        self,
        *,
        contracts: CanonicalContractCatalog,
        planner: RuntimePlanner,
        model_gateway: ModelGateway,
        tool_client: ToolBoundaryClient,
    ) -> None:
        self._contracts = contracts
        self._planner = planner
        self._model_gateway = model_gateway
        self._tool_client = tool_client

    async def run(
        self,
        definition: AgentDefinition,
        request_payload: Mapping[str, Any],
        authorization: RuntimeAuthorization,
    ) -> dict[str, Any]:
        try:
            request = self._contracts.validate(
                AGENT_RUN_REQUEST_SCHEMA,
                request_payload,
            )
        except ContractValidationError as exc:
            raise RuntimeRequestRejected(str(exc)) from exc

        started = datetime.now(UTC)
        started_clock = monotonic()
        tool_results: list[dict[str, Any]] = []
        try:
            budget = self._validate_authorization(definition, request, authorization)
            timeout = budget.timeout_seconds
            if timeout is None:
                return await self._execute(
                    definition,
                    request,
                    authorization,
                    budget,
                    started,
                    started_clock,
                    tool_results,
                )
            async with asyncio.timeout(timeout):
                return await self._execute(
                    definition,
                    request,
                    authorization,
                    budget,
                    started,
                    started_clock,
                    tool_results,
                )
        except TimeoutError:
            failure = RuntimeFailure(
                "RUNTIME_TIMEOUT",
                "Agent runtime exceeded the authorized execution timeout.",
                retryable=True,
            )
        except RuntimeFailure as exc:
            failure = exc
        except Exception:
            failure = RuntimeFailure(
                "RUNTIME_EXECUTION_FAILED",
                "Agent runtime failed safely.",
                output_state="NEEDS_REVIEW",
            )
        result = self._failure_result(request, started, failure, tool_results)
        return self._contracts.validate(AGENT_RUN_RESULT_SCHEMA, result)

    async def _execute(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        authorization: RuntimeAuthorization,
        budget: ExecutionBudget,
        started: datetime,
        started_clock: float,
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._validate_json_schema(
            definition.input_schema, request["input"], "INPUT_SCHEMA_INVALID"
        )
        plan = await self._planner.plan(definition, request)
        self._enforce_plan_limits(plan.tool_calls, budget)
        requested_tool_ids = frozenset(cast(list[str], request.get("requested_tool_ids", [])))
        allowed_by_definition = frozenset(definition.allowed_tool_ids)
        allowed_by_backend = frozenset(authorization.allowed_tool_ids)
        context = cast(dict[str, Any], request["execution_context"])
        correlation_id = str(context["correlation_id"])

        for index, intent in enumerate(plan.tool_calls, 1):
            if intent.tool_id not in requested_tool_ids:
                raise RuntimeFailure(
                    "TOOL_NOT_REQUESTED",
                    "Planned tool is outside AgentRunRequest tool intent.",
                )
            if intent.tool_id not in allowed_by_definition:
                raise RuntimeFailure(
                    "TOOL_NOT_DEFINED",
                    "Planned tool is outside the Agent definition allowlist.",
                )
            if intent.tool_id not in allowed_by_backend:
                raise RuntimeFailure(
                    "TOOL_NOT_AUTHORIZED",
                    "Backend execution authorization does not allow the planned tool.",
                )
            tool_request = self._tool_request(request, intent.tool_id, intent.arguments, index)
            tool_result = await self._tool_client.execute(
                tool_request,
                correlation_id=correlation_id,
            )
            tool_results.append(tool_result)
            if tool_result["status"] not in {"SUCCESS", "COMPLETED"}:
                error = cast(dict[str, Any], tool_result.get("error", {}))
                raise RuntimeFailure(
                    str(error.get("code", "TOOL_EXECUTION_BLOCKED")),
                    "Backend ToolExecutor did not return a successful result.",
                    retryable=bool(error.get("retryable", False)),
                )

        messages = list(plan.messages)
        if tool_results:
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {"governed_tool_results": tool_results},
                        sort_keys=True,
                    ),
                }
            )
        maximum_tokens = budget.max_tokens
        if maximum_tokens is None:
            raise RuntimeFailure("BUDGET_REQUIRED", "max_tokens is required for model access.")
        response = await self._model_gateway.complete(
            ModelRequest(
                run_id=str(request["run_id"]),
                correlation_id=correlation_id,
                policy_ref=definition.model_policy_ref,
                purpose=definition.purpose,
                data_classification=context["data_classification"],
                messages=tuple(messages),
                requested_max_tokens=maximum_tokens,
                budget=budget,
            )
        )
        if budget.max_cost is not None and response.cost is not None:
            if response.cost > budget.max_cost:
                raise RuntimeFailure(
                    "BUDGET_COST_EXCEEDED",
                    "Model response exceeded the authorized cost budget.",
                )
        output = self._parse_output(response)
        self._validate_json_schema(definition.output_schema, output, "OUTPUT_SCHEMA_INVALID")
        result = self._success_result(
            request,
            started,
            started_clock,
            output,
            response,
            tool_results,
        )
        return self._contracts.validate(AGENT_RUN_RESULT_SCHEMA, result)

    @staticmethod
    def _validate_authorization(
        definition: AgentDefinition,
        request: dict[str, Any],
        authorization: RuntimeAuthorization,
    ) -> ExecutionBudget:
        if authorization.run_id != request["run_id"]:
            raise RuntimeFailure(
                "RUN_AUTHORIZATION_MISMATCH", "Run authorization does not match run_id."
            )
        if authorization.lifecycle_state not in {"ACTIVE", "TEST_AUTHORIZED"}:
            raise RuntimeFailure(
                "AGENT_LIFECYCLE_DENIED", "Backend did not authorize Agent lifecycle."
            )
        if (
            definition.agent_id != request["agent_id"]
            or definition.agent_version != request["agent_version"]
        ):
            raise RuntimeFailure(
                "AGENT_VERSION_MISMATCH", "Agent definition does not match request."
            )
        if request["capability_id"] not in definition.capability_ids:
            raise RuntimeFailure(
                "CAPABILITY_MISMATCH", "Capability is not present in Agent definition."
            )
        context = cast(dict[str, Any], request["execution_context"])
        raw_budget = context.get("execution_budget")
        if not isinstance(raw_budget, dict):
            raise RuntimeFailure(
                "BUDGET_REQUIRED", "ExecutionContext must carry an execution budget."
            )
        return ExecutionBudget.model_validate(raw_budget)

    @staticmethod
    def _enforce_plan_limits(tool_calls: tuple[Any, ...], budget: ExecutionBudget) -> None:
        steps = len(tool_calls) + 1
        if budget.max_steps is not None and steps > budget.max_steps:
            raise RuntimeFailure("BUDGET_STEPS_EXCEEDED", "Execution plan exceeds max_steps.")
        if budget.max_tool_calls is not None and len(tool_calls) > budget.max_tool_calls:
            raise RuntimeFailure(
                "BUDGET_TOOL_CALLS_EXCEEDED", "Execution plan exceeds max_tool_calls."
            )

    @staticmethod
    def _validate_json_schema(schema: Mapping[str, Any], payload: Any, code: str) -> None:
        errors = sorted(
            Draft202012Validator(dict(schema)).iter_errors(payload),
            key=lambda item: list(item.path),
        )
        if errors:
            raise RuntimeFailure(code, "Runtime payload does not satisfy the Agent schema.")

    @staticmethod
    def _tool_request(
        request: dict[str, Any],
        tool_id: str,
        arguments: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        seed = f"{request['run_id']}:{index}:{tool_id}".encode()
        suffix = hashlib.sha256(seed).hexdigest()[:20]
        return {
            "tool_call_id": f"toolcall_{suffix}",
            "run_id": request["run_id"],
            "tool_id": tool_id,
            "execution_context": request["execution_context"],
            "arguments": arguments,
            "requested_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _parse_output(response: ModelResponse) -> Any:
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise RuntimeFailure(
                "MODEL_OUTPUT_INVALID_JSON",
                "Model output is not valid JSON.",
                output_state="NEEDS_REVIEW",
            ) from exc

    @staticmethod
    def _success_result(
        request: dict[str, Any],
        started: datetime,
        started_clock: float,
        output: Any,
        response: ModelResponse,
        tool_results: list[dict[str, Any]],
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
            "status": "COMPLETED",
            "output_state": "AI_INFERRED",
            "output": output,
            "usage": {
                "provider": response.route_id,
                "model": response.route_id,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_milliseconds": max(0, int((monotonic() - started_clock) * 1000)),
                **({"estimated_cost": response.cost} if response.cost is not None else {}),
            },
            "tool_results": list(tool_results),
            "evidence_refs": [],
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _failure_result(
        request: dict[str, Any],
        started: datetime,
        failure: RuntimeFailure,
        tool_results: list[dict[str, Any]],
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
            "status": "FAILED",
            "output_state": failure.output_state,
            "tool_results": list(tool_results),
            "evidence_refs": [],
            "error": {
                "code": failure.code,
                "message": failure.message,
                "correlation_id": context["correlation_id"],
                "retryable": failure.retryable,
            },
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
