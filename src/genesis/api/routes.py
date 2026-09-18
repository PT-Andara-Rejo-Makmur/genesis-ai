from fastapi import APIRouter, Depends, Request

from genesis import __version__
from genesis.api.auth import verify_service_token
from genesis.api.errors import InternalBoundaryError
from genesis.api.models import HealthResponse, IntegrationDiagnosticResponse, SystemInfoResponse
from genesis.config import Settings
from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.control_plane.factory import (
    CapabilityFactory,
    FactoryAnalysisRequest,
    FactoryAnalysisResult,
)
from genesis.observability.correlation import current_correlation_id

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_service_token)],
)


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def internal_health() -> HealthResponse:
    """Authenticated liveness signal for Backend-to-GENESIS connectivity."""

    return HealthResponse()


@router.get("/system/info", response_model=SystemInfoResponse)
async def system_info(_request: Request) -> SystemInfoResponse:
    return SystemInfoResponse(version=__version__)


@router.get("/system/integration", response_model=IntegrationDiagnosticResponse)
async def integration_diagnostic(_request: Request) -> IntegrationDiagnosticResponse:
    """Prove reachability without accessing a provider or business database."""

    return IntegrationDiagnosticResponse(correlation_id=current_correlation_id())


@router.post("/factory/analyze", response_model=FactoryAnalysisResult)
async def analyze_factory(
    payload: FactoryAnalysisRequest,
    request: Request,
) -> FactoryAnalysisResult:
    """Produce canonical drafts; never register, approve, or release them."""

    correlation_id = current_correlation_id()
    if payload.requirement.execution_context.correlation_id != correlation_id:
        raise InternalBoundaryError(
            "CORRELATION_ID_MISMATCH",
            "Payload correlation_id must match X-Correlation-ID.",
            status_code=422,
        )
    settings: Settings = request.app.state.settings
    if settings.ALOS_CONTRACTS_PATH is None:
        raise InternalBoundaryError(
            "CONTRACT_CATALOG_NOT_CONFIGURED",
            "ALOS_CONTRACTS_PATH is required for factory contract validation.",
            status_code=503,
        )
    try:
        catalog = CanonicalContractCatalog(settings.ALOS_CONTRACTS_PATH)
        return CapabilityFactory(contracts=catalog).analyze(payload)
    except (ContractValidationError, ValueError) as exc:
        raise InternalBoundaryError(
            "FACTORY_CONTRACT_INVALID",
            str(exc),
            status_code=422,
        ) from exc
