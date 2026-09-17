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
        return await adapter.complete(request, route_id=route_id)
