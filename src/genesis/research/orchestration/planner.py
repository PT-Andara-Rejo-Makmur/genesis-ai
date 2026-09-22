"""Bounded ModelGateway-only H7 question decomposition."""

from __future__ import annotations

import json
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from genesis.model_gateway.interfaces import ModelGateway
from genesis.model_gateway.types import ModelRequest
from genesis.research.domains import domain_profile
from genesis.research.models import ResearchDomain
from genesis.research.orchestration.models import (
    ModelCallUsage,
    ResearchOrchestrationFailure,
    ResearchPlan,
    ResearchSubquery,
)
from genesis.runtime.limits import ExecutionBudget


class _PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subqueries: tuple[ResearchSubquery, ...] = Field(min_length=1, max_length=8)
    limitations: tuple[str, ...] = ()


class PlannedResearch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan: ResearchPlan
    usage: ModelCallUsage


class ResearchQuestionPlanner:
    """Create one strict plan; it cannot express or grant tool authority."""

    def __init__(self, *, model_gateway: ModelGateway, max_subqueries: int = 8) -> None:
        if not 1 <= max_subqueries <= 8:
            raise ValueError("max_subqueries must be between 1 and 8")
        self._model_gateway = model_gateway
        self._max_subqueries = max_subqueries

    async def plan(
        self,
        *,
        research_id: str,
        run_id: str,
        correlation_id: str,
        domain: ResearchDomain,
        question: str,
        scope_refs: tuple[str, ...],
        data_classification: str,
        budget: ExecutionBudget,
    ) -> PlannedResearch:
        maximum_tokens = min(1_000, budget.max_tokens or 1_000)
        profile = domain_profile(domain)
        response = await self._model_gateway.complete(
            ModelRequest(
                run_id=run_id,
                correlation_id=correlation_id,
                policy_ref="policy.h7.research-plan.v1",
                purpose="bounded-research-question-decomposition",
                data_classification=data_classification,
                messages=(
                    {
                        "role": "system",
                        "content": (
                            "Return only strict JSON containing subqueries and limitations. "
                            f"At most {self._max_subqueries} subqueries. Each subquery must use "
                            f"domain {domain.value}, only supplied scope refs, an evidence need, "
                            "preferred source categories, materiality, and an audit-safe reason "
                            "code. Never emit tools, permissions, credentials, agents, or private "
                            "reasoning."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "research_id": research_id,
                                "question": question,
                                "domain_profile": profile.model_dump(mode="json"),
                                "authorized_scope_refs": scope_refs,
                            },
                            sort_keys=True,
                        ),
                    },
                ),
                requested_max_tokens=maximum_tokens,
                budget=budget.model_copy(update={"max_tokens": maximum_tokens}),
            )
        )
        try:
            draft = _PlanDraft.model_validate_json(response.content)
        except ValidationError as exc:
            raise ResearchOrchestrationFailure(
                "RESEARCH_PLAN_INVALID",
                "ModelGateway returned an invalid bounded research plan.",
                correlation_id,
            ) from exc
        if len(draft.subqueries) > self._max_subqueries:
            raise ResearchOrchestrationFailure(
                "RESEARCH_PLAN_LIMIT_EXCEEDED",
                "Research plan exceeds the authorized subquery bound.",
                correlation_id,
            )
        authorized_scopes = set(scope_refs)
        if any(
            item.domain is not domain
            or not set(item.required_scope_refs).issubset(authorized_scopes)
            for item in draft.subqueries
        ):
            raise ResearchOrchestrationFailure(
                "RESEARCH_PLAN_AUTHORITY_EXPANSION",
                "Research plan expanded domain or scope authority.",
                correlation_id,
            )
        usage = ModelCallUsage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=response.cost or 0,
            route_ids=(response.route_id,),
        )
        if usage.total_tokens > maximum_tokens or (
            budget.max_cost is not None and usage.estimated_cost > budget.max_cost
        ):
            raise ResearchOrchestrationFailure(
                "RESEARCH_MODEL_BUDGET_EXCEEDED",
                "Research planning exceeded the model budget.",
                correlation_id,
            )
        return PlannedResearch(
            plan=ResearchPlan(
                research_id=research_id,
                domain=domain,
                original_question=question,
                subqueries=draft.subqueries,
                max_subqueries=self._max_subqueries,
                limitations=draft.limitations,
            ),
            usage=usage,
        )


def execution_budget(context: Mapping[str, object]) -> ExecutionBudget:
    raw = context.get("execution_budget")
    if not isinstance(raw, Mapping):
        raise ValueError("ExecutionContext requires execution_budget")
    return ExecutionBudget.model_validate(dict(raw))
