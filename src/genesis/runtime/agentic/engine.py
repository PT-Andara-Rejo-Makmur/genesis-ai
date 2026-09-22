"""Bounded generic agentic runtime under Backend-issued authority."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

from genesis.agents.definitions import AgentDefinition
from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest
from genesis.orchestration.delegation import (
    ChildResultInvalid,
    ChildResultValidator,
    DelegationAuthorizationSnapshot,
    DelegationBoundaryClient,
    DelegationDenied,
    DelegationGuard,
    DelegationPlanner,
    DelegationPlanningError,
)
from genesis.runtime.agentic.boundary import (
    failure_result,
    parse_output,
    terminal_result,
    tool_request,
    validate_json_schema,
    validate_json_schema_with_state,
    validate_tool_result,
)
from genesis.runtime.agentic.cancellation import NeverCancelled, NullRuntimeObserver
from genesis.runtime.agentic.models import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    ExecutionPlan,
    RuntimeAuthorization,
    RuntimeFailure,
    RuntimeRequestRejected,
    StopReason,
    ToolCallIntent,
    ToolObservation,
)
from genesis.runtime.agentic.protocols import (
    AgenticPlanner,
    CancellationProbe,
    RuntimeObserver,
    RuntimePlanner,
    ToolBoundaryClient,
)
from genesis.runtime.agentic.state import (
    account_model_response,
    account_planner_usage,
    enforce_cumulative_budget,
    fail,
    initial_state,
    known_evidence,
    required_limit,
    select_evidence,
)
from genesis.runtime.agentic.stopping import StoppingPolicy
from genesis.runtime.limits import ExecutionBudget

AGENT_RUN_REQUEST_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-run-request.schema.json"
AGENT_RUN_RESULT_SCHEMA = "https://schemas.alos.dev/v1/agent/agent-run-result.schema.json"
TOOL_REQUEST_SCHEMA = "https://schemas.alos.dev/v1/tool/tool-request.schema.json"
TOOL_RESULT_SCHEMA = "https://schemas.alos.dev/v1/tool/tool-result.schema.json"


class AgentRuntimeEngine:
    """Iterate through operational decisions with deterministic, cumulative bounds."""

    def __init__(
        self,
        *,
        contracts: CanonicalContractCatalog,
        planner: RuntimePlanner | AgenticPlanner,
        model_gateway: ModelGateway,
        tool_client: ToolBoundaryClient,
        cancellation_probe: CancellationProbe | None = None,
        observer: RuntimeObserver | None = None,
        delegation_client: DelegationBoundaryClient | None = None,
        delegation_authorization: DelegationAuthorizationSnapshot | None = None,
    ) -> None:
        self._contracts = contracts
        self._planner = planner
        self._model_gateway = model_gateway
        self._tool_client = tool_client
        self._cancellation = cancellation_probe or NeverCancelled()
        self._observer = observer or NullRuntimeObserver()
        self._delegation_client = delegation_client
        self._delegation_authorization = delegation_authorization
        self._delegation_guard = DelegationGuard()
        self._child_validator = ChildResultValidator(contracts)

    async def run(
        self,
        definition: AgentDefinition,
        request_payload: Mapping[str, Any],
        authorization: RuntimeAuthorization,
    ) -> dict[str, Any]:
        try:
            request = self._contracts.validate(AGENT_RUN_REQUEST_SCHEMA, request_payload)
        except ContractValidationError as exc:
            raise RuntimeRequestRejected(str(exc)) from exc

        started = datetime.now(UTC)
        started_clock = monotonic()
        tool_results: list[dict[str, Any]] = []
        state: AgenticRuntimeState | None = None
        try:
            budget = self._validate_authorization(definition, request, authorization)
            state = initial_state(request, budget)
            if budget.timeout_seconds is None:
                return await self._execute(
                    definition,
                    request,
                    authorization,
                    budget,
                    started,
                    started_clock,
                    state,
                    tool_results,
                )
            async with asyncio.timeout(budget.timeout_seconds):
                return await self._execute(
                    definition,
                    request,
                    authorization,
                    budget,
                    started,
                    started_clock,
                    state,
                    tool_results,
                )
        except TimeoutError:
            timeout_projection = StoppingPolicy().project(StopReason.TIMEOUT)
            failure = RuntimeFailure(
                "RUNTIME_TIMEOUT",
                "Agent runtime exceeded the authorized execution timeout.",
                retryable=True,
                output_state=cast(Any, timeout_projection.output_state),
                run_status=cast(Any, timeout_projection.status),
                stop_reason=StopReason.TIMEOUT,
                state=state,
            )
        except RuntimeFailure as exc:
            failure = exc
            state = exc.state or state
        except Exception:
            failure = RuntimeFailure(
                "RUNTIME_EXECUTION_FAILED",
                "Agent runtime failed safely.",
                output_state="NEEDS_REVIEW",
                stop_reason=StopReason.MODEL_FAILED,
                state=state,
            )
        if failure.stop_reason is not None and state is not None:
            self._notify_stop(failure.stop_reason, state)
        result = failure_result(request, started, started_clock, failure, tool_results, state)
        return self._contracts.validate(AGENT_RUN_RESULT_SCHEMA, result)

    async def _execute(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        authorization: RuntimeAuthorization,
        budget: ExecutionBudget,
        started: datetime,
        started_clock: float,
        state: AgenticRuntimeState,
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        validate_json_schema(
            definition.input_schema, request["input"], "INPUT_SCHEMA_INVALID"
        )
        known_evidence_catalog = known_evidence(request)
        legacy_plan: ExecutionPlan | None = None

        while state.step_count < required_limit(budget.max_steps, "max_steps"):
            await self._require_not_cancelled(state)
            if state.remaining_tokens <= 0:
                raise fail(
                    state,
                    "BUDGET_TOKENS_EXHAUSTED",
                    "The cumulative model token budget is exhausted.",
                    StopReason.BUDGET_EXHAUSTED,
                )
            state = state.model_copy(update={"step_count": state.step_count + 1})
            self._safe_notify(self._observer.on_step_started, state)
            planner_request = self._planner_request(
                definition, request, authorization, state
            )
            try:
                decision, legacy_plan = await self._next_decision(
                    definition, planner_request, state, legacy_plan
                )
            except RuntimeFailure:
                raise
            except Exception as exc:
                raise fail(
                    state,
                    "PLANNER_FAILED",
                    "The runtime planner failed safely.",
                    StopReason.MODEL_FAILED,
                    output_state="NEEDS_REVIEW",
                ) from exc
            if not isinstance(decision, AgenticDecision):
                raise fail(
                    state,
                    "PLANNER_OUTPUT_INVALID",
                    "The runtime planner returned an invalid structured decision.",
                    StopReason.OUTPUT_INVALID,
                    output_state="NEEDS_REVIEW",
                )
            state = account_planner_usage(state, decision.planner_usage)
            enforce_cumulative_budget(state)

            if decision.kind is AgenticActionKind.TOOL:
                if definition.approval_required:
                    intent = cast(ToolCallIntent, decision.tool_intent)
                    approval = AgenticDecision(
                        kind=AgenticActionKind.APPROVAL_REQUIRED,
                        output=decision.output,
                        safe_message=(
                            f"Tool action {intent.tool_id} requires Backend governance approval."
                        ),
                        evidence_ids=decision.evidence_ids,
                    )
                    return self._review_result(
                        definition,
                        request,
                        started,
                        started_clock,
                        state,
                        approval,
                        StopReason.APPROVAL_REQUIRED,
                        tool_results,
                        known_evidence_catalog,
                    )
                state = await self._execute_tool_decision(
                    definition,
                    request,
                    authorization,
                    budget,
                    state,
                    decision,
                    tool_results,
                )
                continue
            if decision.kind is AgenticActionKind.DELEGATE:
                state = await self._execute_delegation(
                    request,
                    state,
                    decision,
                    known_evidence_catalog,
                )
                continue
            if decision.kind is AgenticActionKind.FINISH:
                return await self._finish(
                    definition,
                    request,
                    budget,
                    started,
                    started_clock,
                    state,
                    decision,
                    tool_results,
                    known_evidence_catalog,
                )
            if decision.kind in {
                AgenticActionKind.NEEDS_INFO,
                AgenticActionKind.APPROVAL_REQUIRED,
            }:
                reason = (
                    StopReason.NEEDS_INFO
                    if decision.kind is AgenticActionKind.NEEDS_INFO
                    else StopReason.APPROVAL_REQUIRED
                )
                return self._review_result(
                    definition,
                    request,
                    started,
                    started_clock,
                    state,
                    decision,
                    reason,
                    tool_results,
                    known_evidence_catalog,
                )
            raise fail(
                state,
                decision.reason_code or "AGENTIC_DECISION_FAILED",
                decision.safe_message or "The planner stopped with a safe failure.",
                StopReason.EVIDENCE_INSUFFICIENT
                if decision.reason_code == "EVIDENCE_INSUFFICIENT"
                else StopReason.OUTPUT_INVALID,
                output_state="NEEDS_REVIEW",
            )

        raise fail(
            state,
            "BUDGET_STEPS_EXCEEDED",
            "Agent runtime reached the authorized maximum step count.",
            StopReason.MAX_STEPS,
        )

    async def _next_decision(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        state: AgenticRuntimeState,
        legacy_plan: ExecutionPlan | None,
    ) -> tuple[AgenticDecision, ExecutionPlan | None]:
        if isinstance(self._planner, AgenticPlanner):
            return await self._planner.next_action(definition, request, state), None
        plan = legacy_plan or await self._planner.plan(definition, request)
        index = state.step_count - 1
        if index < len(plan.tool_calls):
            return (
                AgenticDecision(
                    kind=AgenticActionKind.TOOL,
                    tool_intent=plan.tool_calls[index],
                ),
                plan,
            )
        return AgenticDecision(kind=AgenticActionKind.FINISH, messages=plan.messages), plan

    async def _execute_tool_decision(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        authorization: RuntimeAuthorization,
        budget: ExecutionBudget,
        state: AgenticRuntimeState,
        decision: AgenticDecision,
        tool_results: list[dict[str, Any]],
    ) -> AgenticRuntimeState:
        intent = cast(ToolCallIntent, decision.tool_intent)
        maximum_tool_calls = required_limit(budget.max_tool_calls, "max_tool_calls")
        if state.tool_call_count >= maximum_tool_calls:
            raise fail(
                state,
                "BUDGET_TOOL_CALLS_EXCEEDED",
                "Agent runtime reached the authorized maximum tool-call count.",
                StopReason.MAX_TOOL_CALLS,
            )
        requested = frozenset(cast(list[str], request.get("requested_tool_ids", [])))
        if intent.tool_id not in requested:
            raise fail(
                state,
                "TOOL_NOT_REQUESTED",
                "Planned tool is outside AgentRunRequest tool intent.",
                StopReason.TOOL_DENIED,
            )
        if intent.tool_id not in definition.allowed_tool_ids:
            raise fail(
                state,
                "TOOL_NOT_DEFINED",
                "Planned tool is outside the Agent definition allowlist.",
                StopReason.TOOL_DENIED,
            )
        if intent.tool_id not in authorization.allowed_tool_ids:
            raise fail(
                state,
                "TOOL_NOT_AUTHORIZED",
                "Backend execution authorization does not allow the planned tool.",
                StopReason.TOOL_DENIED,
            )
        await self._require_not_cancelled(state)
        canonical_tool_request = tool_request(
            request, intent.tool_id, intent.arguments, state.step_count
        )
        try:
            self._contracts.validate(TOOL_REQUEST_SCHEMA, canonical_tool_request)
        except ContractValidationError as exc:
            raise fail(
                state,
                "TOOL_REQUEST_INVALID",
                "Generated ToolRequest does not satisfy the canonical contract.",
                StopReason.OUTPUT_INVALID,
            ) from exc
        self._safe_notify(
            self._observer.on_tool_requested,
            str(canonical_tool_request["tool_call_id"]), intent.tool_id, state.step_count
        )
        context = cast(dict[str, Any], request["execution_context"])
        try:
            raw_result = await self._tool_client.execute(
                canonical_tool_request,
                correlation_id=str(context["correlation_id"]),
            )
            tool_result = self._contracts.validate(TOOL_RESULT_SCHEMA, raw_result)
        except ContractValidationError as exc:
            raise fail(
                state,
                "TOOL_RESULT_INVALID",
                "ToolResult does not satisfy the canonical contract.",
                StopReason.TOOL_FAILED,
            ) from exc
        except Exception as exc:
            raise fail(
                state,
                "TOOL_BOUNDARY_FAILED",
                "Backend ToolExecutor boundary failed safely.",
                StopReason.TOOL_FAILED,
                retryable=True,
            ) from exc
        validate_tool_result(canonical_tool_request, tool_result, state)
        tool_results.append(tool_result)
        error = cast(dict[str, Any], tool_result.get("error", {}))
        observation = ToolObservation(
            step_index=state.step_count,
            tool_call_id=str(tool_result["tool_call_id"]),
            tool_id=intent.tool_id,
            status=tool_result["status"],
            output=tool_result.get("output"),
            error_code=str(error.get("code")) if error.get("code") else None,
        )
        updated = state.model_copy(
            update={
                "tool_call_count": state.tool_call_count + 1,
                "observations": (*state.observations, observation),
            }
        )
        self._safe_notify(
            self._observer.on_tool_result,
            observation.tool_call_id, observation.status, observation.step_index
        )
        if observation.status in {"DENIED", "REJECTED"}:
            raise fail(
                updated,
                f"TOOL_{observation.status}",
                "Backend ToolExecutor denied or rejected the tool action.",
                StopReason.TOOL_DENIED,
            )
        if observation.status in {"FAILED", "TIMEOUT"}:
            raise fail(
                updated,
                f"TOOL_{observation.status}",
                "Backend ToolExecutor returned a failed tool observation.",
                StopReason.TOOL_FAILED,
                retryable=bool(error.get("retryable", False)),
            )
        return updated

    async def _execute_delegation(
        self,
        request: dict[str, Any],
        state: AgenticRuntimeState,
        decision: AgenticDecision,
        known_evidence_catalog: dict[str, dict[str, Any]],
    ) -> AgenticRuntimeState:
        snapshot = self._delegation_authorization
        client = self._delegation_client
        intent = decision.delegation_intent
        if snapshot is None or client is None:
            raise fail(
                state,
                "DELEGATION_NOT_AUTHORIZED",
                "No Backend delegation authorization boundary is available.",
                StopReason.DELEGATION_DENIED,
            )
        if intent is None and decision.delegation_proposal is not None:
            proposal = decision.delegation_proposal
            try:
                intent = DelegationPlanner().plan(
                    snapshot=snapshot,
                    target_agent_id=proposal.target_agent_id,
                    target_agent_version=proposal.target_agent_version,
                    capability_id=proposal.target_capability_id,
                    task=proposal.task,
                    requested_authority=proposal.requested_authority,
                )
            except DelegationPlanningError as exc:
                raise fail(
                    state,
                    "CHILD_TARGET_DENIED",
                    "The proposed exact child target is not authorized.",
                    StopReason.DELEGATION_DENIED,
                ) from exc
        if intent is None:
            raise fail(
                state,
                "DELEGATION_INTENT_REQUIRED",
                "A structured delegation proposal is required.",
                StopReason.DELEGATION_DENIED,
            )
        try:
            self._delegation_guard.validate(
                snapshot,
                intent,
                submitted_keys=state.submitted_delegation_keys,
                reserved_tokens=state.reserved_child_tokens + state.consumed_tokens,
                reserved_cost=state.reserved_child_cost + state.estimated_cost,
                child_count=len(state.child_observations),
            )
        except DelegationDenied as exc:
            raise fail(
                state,
                exc.code,
                "The delegation proposal exceeded the authorized parent envelope.",
                StopReason.DELEGATION_DENIED,
            ) from exc
        await self._require_not_cancelled(state)
        budget = intent.requested_authority.budget
        submitted = state.model_copy(
            update={
                "submitted_delegation_keys": frozenset(
                    (*state.submitted_delegation_keys, intent.delegation_key)
                ),
                "reserved_child_tokens": state.reserved_child_tokens
                + (budget.max_tokens or 0),
                "reserved_child_cost": state.reserved_child_cost + (budget.max_cost or 0),
            }
        )
        try:
            raw_result = await client.submit(intent, correlation_id=state.correlation_id)
        except Exception:
            observation = self._child_validator.invalid_observation(
                intent, "CHILD_BOUNDARY_FAILED"
            )
            return submitted.model_copy(
                update={"child_observations": (*submitted.child_observations, observation)}
            )
        await self._require_not_cancelled(submitted)
        try:
            observation = self._child_validator.validate(
                raw_result,
                intent=intent,
                correlation_id=state.correlation_id,
                parent_authority=snapshot.effective_parent_authority,
            )
        except ChildResultInvalid as exc:
            observation = self._child_validator.invalid_observation(intent, exc.code)
        if observation.validation_status == "VALID":
            for evidence in observation.evidence_refs:
                known_evidence_catalog[str(evidence["evidence_id"])] = evidence
        return submitted.model_copy(
            update={"child_observations": (*submitted.child_observations, observation)}
        )

    async def _finish(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        budget: ExecutionBudget,
        started: datetime,
        started_clock: float,
        state: AgenticRuntimeState,
        decision: AgenticDecision,
        tool_results: list[dict[str, Any]],
        known_evidence: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        selected_evidence = select_evidence(decision, known_evidence, state)
        output = decision.output
        if output is None:
            await self._require_not_cancelled(state)
            if state.remaining_tokens <= 0:
                raise fail(
                    state,
                    "BUDGET_TOKENS_EXHAUSTED",
                    "No token budget remains for final model synthesis.",
                    StopReason.BUDGET_EXHAUSTED,
                )
            messages = list(decision.messages)
            if state.observations:
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "governed_tool_results": tool_results,
                                "instruction_authority": False,
                            },
                            sort_keys=True,
                        ),
                    }
                )
            context = cast(dict[str, Any], request["execution_context"])
            try:
                response = await self._model_gateway.complete(
                    ModelRequest(
                        run_id=state.run_id,
                        correlation_id=state.correlation_id,
                        policy_ref=definition.model_policy_ref,
                        purpose=definition.purpose,
                        data_classification=context["data_classification"],
                        messages=tuple(messages),
                        requested_max_tokens=state.remaining_tokens,
                        budget=budget,
                    )
                )
            except Exception as exc:
                raise fail(
                    state,
                    "MODEL_GATEWAY_FAILED",
                    "ModelGateway failed safely.",
                    StopReason.MODEL_FAILED,
                    output_state="NEEDS_REVIEW",
                ) from exc
            state = account_model_response(state, response)
            enforce_cumulative_budget(state)
            output = parse_output(response, state)
        validate_json_schema_with_state(
            definition.output_schema, output, "OUTPUT_SCHEMA_INVALID", state
        )
        self._notify_stop(StopReason.SUCCESS, state)
        projection = StoppingPolicy().project(StopReason.SUCCESS)
        result = terminal_result(
            request=request,
            started=started,
            started_clock=started_clock,
            state=state,
            status=projection.status,
            output_state=projection.output_state,
            output=output,
            tool_results=tool_results,
            evidence_refs=selected_evidence,
        )
        return self._contracts.validate(AGENT_RUN_RESULT_SCHEMA, result)

    def _review_result(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        started: datetime,
        started_clock: float,
        state: AgenticRuntimeState,
        decision: AgenticDecision,
        reason: StopReason,
        tool_results: list[dict[str, Any]],
        known_evidence: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        output = decision.output or {
            "status": reason.value,
            "reason": decision.safe_message or "Human input or governance is required.",
        }
        validate_json_schema_with_state(
            definition.output_schema, output, "REVIEW_OUTPUT_SCHEMA_INVALID", state
        )
        evidence = select_evidence(decision, known_evidence, state)
        self._notify_stop(reason, state)
        projection = StoppingPolicy().project(reason)
        result = terminal_result(
            request=request,
            started=started,
            started_clock=started_clock,
            state=state,
            status=projection.status,
            output_state=projection.output_state,
            output=output,
            tool_results=tool_results,
            evidence_refs=evidence,
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
        budget = ExecutionBudget.model_validate(raw_budget)
        required_limit(budget.max_steps, "max_steps")
        required_limit(budget.max_tool_calls, "max_tool_calls")
        required_limit(budget.max_tokens, "max_tokens")
        return budget

    async def _require_not_cancelled(self, state: AgenticRuntimeState) -> None:
        if await self._cancellation.is_cancelled(state.run_id):
            raise fail(
                state,
                "RUNTIME_CANCELLED",
                "The run was cancelled by the external control boundary.",
                StopReason.CANCELLED,
                run_status="CANCELLED",
            )

    def _notify_stop(self, reason: StopReason, state: AgenticRuntimeState) -> None:
        self._safe_notify(self._observer.on_stop, reason, state)

    def _safe_notify(self, callback: Callable[..., None], *args: Any) -> None:
        try:
            callback(*args)
        except Exception:
            return

    def _planner_request(
        self,
        definition: AgentDefinition,
        request: dict[str, Any],
        authorization: RuntimeAuthorization,
        state: AgenticRuntimeState,
    ) -> dict[str, Any]:
        effective = sorted(
            set(cast(list[str], request.get("requested_tool_ids", [])))
            .intersection(definition.allowed_tool_ids)
            .intersection(authorization.allowed_tool_ids)
        )
        projection: dict[str, Any] = {**request, "requested_tool_ids": effective}
        snapshot = self._delegation_authorization
        if snapshot is not None and snapshot.enabled:
            authority = snapshot.effective_parent_authority
            projection["_delegation"] = {
                "authorized_child_targets": [
                    {
                        "agent_id": item.agent_id,
                        "agent_version": item.agent_version,
                        "capability_ids": item.capability_ids,
                        "research_domains": item.research_domains,
                    }
                    for item in snapshot.allowed_child_targets
                ],
                "parent_depth": snapshot.parent_depth,
                "max_depth": snapshot.max_depth,
                "remaining_child_capacity": max(
                    0, snapshot.max_children - len(state.child_observations)
                ),
                "allowed_narrowing": {
                    "permission_refs": sorted(authority.permission_refs),
                    "scope_refs": sorted(authority.scope_refs),
                    "allowed_tool_ids": sorted(authority.allowed_tool_ids),
                    "data_classification": authority.data_classification,
                },
                "parent_budget": snapshot.parent_budget.model_dump(mode="json"),
                "research_constraints": (
                    snapshot.research_constraints.model_dump(mode="json")
                    if snapshot.research_constraints is not None
                    else None
                ),
            }
        return projection
