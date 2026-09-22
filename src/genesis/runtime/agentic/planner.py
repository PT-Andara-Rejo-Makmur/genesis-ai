"""Generic planners for bounded agent execution."""

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from genesis.agents.definitions import AgentDefinition
from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest
from genesis.orchestration.delegation import DelegationSynthesizer
from genesis.runtime.agentic.models import (
    AgenticActionKind,
    AgenticDecision,
    AgenticRuntimeState,
    ExecutionPlan,
    ModelUsage,
    RuntimeFailure,
    StopReason,
)
from genesis.runtime.limits import ExecutionBudget

_MAX_OBSERVATIONS = 8
_MAX_OUTPUT_PREVIEW = 2_000
_MAX_CHILD_OUTPUT_PREVIEW = 3_000


class ModelGatewayAgenticPlanner:
    """Ask ModelGateway for one strict operational decision per bounded step."""

    def __init__(self, *, model_gateway: ModelGateway) -> None:
        self._model_gateway = model_gateway

    async def next_action(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        context = request["execution_context"]
        if not isinstance(context, Mapping):
            raise self._invalid(state)
        remaining_budget = self._remaining_budget(context, state)
        delegation_available = bool(request.get("_delegation"))
        allowed_actions = (
            "TOOL, DELEGATE, FINISH, NEEDS_INFO, APPROVAL_REQUIRED, and FAIL"
            if delegation_available
            else "TOOL, FINISH, NEEDS_INFO, APPROVAL_REQUIRED, and FAIL"
        )
        delegation_instruction = (
            " DELEGATE requires delegation_proposal using an exact listed target and a "
            "narrower authority envelope. Do not create lineage, run IDs, or delegation keys."
            if delegation_available
            else ""
        )
        response = await self._model_gateway.complete(
            ModelRequest(
                run_id=state.run_id,
                correlation_id=state.correlation_id,
                policy_ref=definition.model_policy_ref,
                purpose=definition.purpose,
                data_classification=str(context["data_classification"]),
                messages=(
                    {
                        "role": "system",
                        "content": (
                            "Choose exactly one bounded operational action. Return only JSON "
                            f"matching AgenticDecision. Allowed actions are {allowed_actions}. "
                            "TOOL requires tool_intent."
                            f"{delegation_instruction} "
                            "The tool_intent must contain tool_id and arguments. Never invent "
                            "authority, "
                            "credentials, evidence, tools, or hidden reasoning."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            self._operational_input(definition, request, state),
                            sort_keys=True,
                            default=str,
                        ),
                    },
                ),
                requested_max_tokens=state.remaining_tokens,
                budget=remaining_budget,
            )
        )
        usage = ModelUsage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=response.cost,
            route_id=response.route_id,
        )
        try:
            raw_decision = json.loads(response.content)
            if not isinstance(raw_decision, dict) or "planner_usage" in raw_decision:
                raise ValueError("planner_usage is runtime-owned")
            decision = AgenticDecision.model_validate_json(response.content, strict=True)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            raise self._invalid(state, usage) from exc
        return decision.model_copy(
            update={"planner_usage": usage}
        )

    @staticmethod
    def _remaining_budget(
        context: Mapping[str, Any], state: AgenticRuntimeState
    ) -> ExecutionBudget:
        raw = context.get("execution_budget")
        if not isinstance(raw, Mapping):
            raise RuntimeFailure("BUDGET_REQUIRED", "Execution budget is required.")
        budget = ExecutionBudget.model_validate(dict(raw))
        remaining_cost = (
            max(0.0, state.max_cost - state.estimated_cost)
            if state.max_cost is not None
            else None
        )
        return budget.model_copy(
            update={"max_tokens": state.remaining_tokens, "max_cost": remaining_cost}
        )

    @staticmethod
    def _operational_input(
        definition: AgentDefinition,
        request: Mapping[str, Any],
        state: AgenticRuntimeState,
    ) -> dict[str, Any]:
        bundle = request.get("context_bundle")
        evidence = bundle.get("evidence_refs", []) if isinstance(bundle, Mapping) else []
        evidence_metadata = [
            {
                key: item.get(key)
                for key in (
                    "evidence_id",
                    "source_id",
                    "data_classification",
                    "freshness",
                    "reliability",
                    "content_trust",
                )
            }
            for item in evidence
            if isinstance(item, Mapping)
            and item.get("evidence_id") in state.known_evidence_ids
        ]
        observations = []
        for item in state.observations[-_MAX_OBSERVATIONS:]:
            preview = json.dumps(item.output, sort_keys=True, default=str)
            observations.append(
                {
                    "step_index": item.step_index,
                    "tool_call_id": item.tool_call_id,
                    "tool_id": item.tool_id,
                    "status": item.status,
                    "error_code": item.error_code,
                    "output_preview": preview[:_MAX_OUTPUT_PREVIEW],
                }
            )
        synthesis = (
            DelegationSynthesizer().synthesize(state.child_observations)
            if state.child_observations
            else None
        )
        return {
            "agent_purpose": definition.purpose,
            "user_input": request["input"],
            "allowed_tool_ids": list(request.get("requested_tool_ids", [])),
            "prior_observations": observations,
            "child_observations": [
                {
                    "child_task_id": item.child_task_id,
                    "target_agent_id": item.target_agent_id,
                    "target_agent_version": item.target_agent_version,
                    "status": item.status,
                    "validation_status": item.validation_status,
                    "error_code": item.error_code,
                    "output_preview": json.dumps(
                        item.output, sort_keys=True, default=str
                    )[:_MAX_CHILD_OUTPUT_PREVIEW],
                    "instruction_authority": False,
                }
                for item in state.child_observations
            ],
            "delegation_synthesis": (
                {
                    "disposition": synthesis.disposition,
                    "successful_child_task_ids": [
                        item.child_task_id for item in synthesis.successful_children
                    ],
                    "failed_child_task_ids": [
                        item.child_task_id for item in synthesis.failed_children
                    ],
                    "evidence_ids": [
                        item["evidence_id"] for item in synthesis.evidence_refs
                    ],
                    "reason_codes": synthesis.reason_codes,
                    "instruction_authority": False,
                }
                if synthesis is not None
                else None
            ),
            **(
                {"delegation": request["_delegation"]}
                if request.get("_delegation") is not None
                else {}
            ),
            "evidence": evidence_metadata,
            "remaining_budget": {
                "tokens": state.remaining_tokens,
                "cost": (
                    max(0.0, state.max_cost - state.estimated_cost)
                    if state.max_cost is not None
                    else None
                ),
            },
            "output_schema": definition.output_schema,
        }

    @staticmethod
    def _invalid(
        state: AgenticRuntimeState, usage: ModelUsage | None = None
    ) -> RuntimeFailure:
        if usage is not None:
            state = state.model_copy(
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
        return RuntimeFailure(
            "PLANNER_OUTPUT_INVALID",
            "The model planner returned an invalid structured decision.",
            output_state="NEEDS_REVIEW",
            stop_reason=StopReason.OUTPUT_INVALID,
            state=state,
        )


class SinglePassPlanner:
    async def plan(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
    ) -> ExecutionPlan:
        return ExecutionPlan(
            messages=(
                {
                    "role": "system",
                    "content": definition.purpose,
                },
                {
                    "role": "user",
                    "content": json.dumps(request["input"], sort_keys=True),
                },
            )
        )

    async def next_action(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision:
        del state
        plan = await self.plan(definition, request)
        return AgenticDecision(kind=AgenticActionKind.FINISH, messages=plan.messages)
