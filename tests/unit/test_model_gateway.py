import pytest

from genesis.model_gateway import GovernedModelGateway, ModelRequest, ModelResponse
from genesis.model_gateway.budget import BudgetExceeded, ExecutionBudgetGuard
from genesis.model_gateway.policy import StaticModelPolicy
from genesis.model_gateway.routing import StaticModelRouter
from genesis.runtime.limits import ExecutionBudget


class DeterministicProvider:
    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        return ModelResponse(
            content=f"response:{request.purpose}",
            route_id=route_id,
            input_tokens=10,
            output_tokens=5,
        )


def request(max_tokens: int = 100) -> ModelRequest:
    return ModelRequest(
        run_id="run_model_001",
        correlation_id="corr_model_001",
        policy_ref="policy.standard",
        purpose="classification",
        messages=({"role": "user", "content": "classify"},),
        requested_max_tokens=max_tokens,
        budget=ExecutionBudget(max_tokens=100),
    )


@pytest.mark.asyncio
async def test_model_gateway_routes_through_policy_budget_and_adapter() -> None:
    gateway = GovernedModelGateway(
        policy=StaticModelPolicy(frozenset({"policy.standard"})),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            routes={"route.test": DeterministicProvider()},
            policy_routes={"policy.standard": "route.test"},
        ),
    )
    result = await gateway.complete(request())
    assert result.route_id == "route.test"
    assert result.content == "response:classification"


@pytest.mark.asyncio
async def test_model_gateway_rejects_budget_overrun_before_provider() -> None:
    gateway = GovernedModelGateway(
        policy=StaticModelPolicy(frozenset({"policy.standard"})),
        budget_guard=ExecutionBudgetGuard(),
        router=StaticModelRouter(
            routes={"route.test": DeterministicProvider()},
            policy_routes={"policy.standard": "route.test"},
        ),
    )
    with pytest.raises(BudgetExceeded):
        await gateway.complete(request(max_tokens=101))
