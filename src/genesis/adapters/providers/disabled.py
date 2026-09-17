from genesis.model_gateway.types import ModelRequest, ModelResponse


class DisabledProviderAdapter:
    """Safe default used when no deployment-managed provider is configured."""

    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse:
        raise RuntimeError(
            f"Model provider route {route_id!r} is disabled for run {request.run_id!r}"
        )
