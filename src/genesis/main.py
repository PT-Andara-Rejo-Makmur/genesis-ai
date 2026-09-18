"""GENESIS FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from genesis.api.auth import InternalAuthError
from genesis.api.errors import InternalBoundaryError
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

    @app.exception_handler(InternalAuthError)
    async def handle_internal_auth_error(_request: Request, exc: InternalAuthError) -> JSONResponse:
        from genesis.observability.correlation import current_correlation_id

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "correlation_id": current_correlation_id(),
                "retryable": False,
            },
        )

    @app.exception_handler(InternalBoundaryError)
    async def handle_internal_boundary_error(
        _request: Request, exc: InternalBoundaryError
    ) -> JSONResponse:
        from genesis.observability.correlation import current_correlation_id

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "correlation_id": current_correlation_id(),
                "retryable": exc.status_code >= 500,
            },
        )

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
