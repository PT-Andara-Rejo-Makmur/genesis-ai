"""GENESIS FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from genesis.api.models import HealthResponse, ReadinessResponse
from genesis.api.routes import router as internal_router
from genesis.config import Settings, get_settings
from genesis.observability.correlation import CorrelationMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started = True
        yield
        app.state.started = False

    app = FastAPI(
        title="GENESIS AI Control Plane",
        version="0.1.0",
        description="Governed AI Control Plane for ALOS.",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.started = False
    app.add_middleware(CorrelationMiddleware)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/ready", response_model=ReadinessResponse, tags=["system"])
    async def ready(request: Request) -> ReadinessResponse:
        current: Settings = request.app.state.settings
        return ReadinessResponse(backend_configured=bool(current.ALOS_BACKEND_BASE_URL))

    app.include_router(internal_router)
    return app


app = create_app()
