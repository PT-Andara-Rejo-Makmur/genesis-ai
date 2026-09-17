from __future__ import annotations

from typing import Protocol

from genesis.model_gateway.types import ModelRequest, ModelResponse


class ModelProviderAdapter(Protocol):
    async def complete(self, request: ModelRequest, *, route_id: str) -> ModelResponse: ...


class ModelPolicy(Protocol):
    def authorize(self, request: ModelRequest) -> None: ...


class ModelBudgetGuard(Protocol):
    def validate(self, request: ModelRequest) -> None: ...


class ModelRouter(Protocol):
    def route(self, request: ModelRequest) -> tuple[str, ModelProviderAdapter]: ...


class ModelGateway(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
