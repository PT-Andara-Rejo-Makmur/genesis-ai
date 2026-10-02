from genesis.model_gateway.budget.guard import BudgetExceeded
from genesis.model_gateway.interfaces import ModelBudgetGuard, ModelPolicy, ModelRouter
from genesis.model_gateway.types import ModelRequest, ModelResponse


class GovernedModelGateway:
    def __init__(
        self,
        *,
        policy: ModelPolicy,
        budget_guard: ModelBudgetGuard,
        router: ModelRouter,
    ) -> None:
        self._policy = policy
        self._budget_guard = budget_guard
        self._router = router

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self._policy.authorize(request)
        self._budget_guard.validate(request)
        route_id, adapter = self._router.route(request)
        response = await adapter.complete(request, route_id=route_id)
        if (
            request.budget.max_tokens is not None
            and response.input_tokens + response.output_tokens > request.budget.max_tokens
        ):
            raise BudgetExceeded(
                "Reported provider tokens exceed the execution budget", response=response
            )
        if (
            request.budget.max_cost is not None
            and response.cost is not None
            and response.cost > request.budget.max_cost
        ):
            raise BudgetExceeded(
                "Reported provider cost exceeds the execution budget", response=response
            )
        return response
