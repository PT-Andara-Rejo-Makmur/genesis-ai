from genesis.model_gateway.interfaces import ModelProviderAdapter
from genesis.model_gateway.types import ModelRequest


class ModelRouteUnavailable(Exception):
    pass


class StaticModelRouter:
    def __init__(
        self,
        routes: dict[str, ModelProviderAdapter],
        policy_routes: dict[str, str],
    ) -> None:
        self._routes = routes
        self._policy_routes = policy_routes

    def route(self, request: ModelRequest) -> tuple[str, ModelProviderAdapter]:
        route_id = self._policy_routes.get(request.policy_ref)
        adapter = self._routes.get(route_id) if route_id else None
        if route_id is None or adapter is None:
            raise ModelRouteUnavailable(f"No model route for policy {request.policy_ref}")
        return route_id, adapter
