from typing import Any

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
from genesis.research import (
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchDecisionFailure,
    ResearchDecisionRequest,
    ResearchRisk,
)

RESEARCH_ANALYSIS_REQUEST_SCHEMA = (
    "https://schemas.alos.dev/v1/research/research-analysis-request.schema.json"
)

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


@router.post("/research")
async def decide_research_source(
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Return a research decision; all retrieval remains a Backend operation."""

    correlation_id = current_correlation_id()
    settings: Settings = request.app.state.settings
    if settings.ALOS_CONTRACTS_PATH is None:
        raise InternalBoundaryError(
            "CONTRACT_CATALOG_NOT_CONFIGURED",
            "ALOS_CONTRACTS_PATH is required for research contract validation.",
            status_code=503,
        )
    try:
        catalog = CanonicalContractCatalog(settings.ALOS_CONTRACTS_PATH)
        validated = catalog.validate(RESEARCH_ANALYSIS_REQUEST_SCHEMA, payload)
        context = validated["execution_context"]
        if not isinstance(context, dict):
            raise ValueError("execution_context must be an object")
        if context["correlation_id"] != correlation_id:
            raise InternalBoundaryError(
                "CORRELATION_ID_MISMATCH",
                "Payload correlation_id must match X-Correlation-ID.",
                status_code=422,
            )
        permissions = tuple(str(item) for item in context.get("permission_refs", []))
        tools = tuple(str(item) for item in context.get("allowed_tool_ids", []))
        scopes = tuple(str(item) for item in context["scope_refs"])
        budget = context.get("execution_budget", {})
        maximum_cost = float(budget.get("max_cost", 0)) if isinstance(budget, dict) else 0
        external_requested = validated["source_mode"] == "EXTERNAL"
        decision_request = ResearchDecisionRequest(
            correlation_id=correlation_id,
            domain=validated["domain"],
            question=str(validated["question"]),
            risk=ResearchRisk.MEDIUM,
            data_classification=context["data_classification"],
            authorized_scope_refs=scopes,
            authorized_permission_refs=permissions,
            allowed_tool_ids=tools,
            information_complete=True,
            external=ExternalResearchBoundary(
                enabled=external_requested,
                estimated_cost=0,
            ),
            maximum_external_cost=maximum_cost,
        )
        return ExternalResearchDecider(contracts=catalog).decide(decision_request).as_canonical()
    except InternalBoundaryError:
        raise
    except ResearchDecisionFailure as exc:
        raise InternalBoundaryError(exc.code, exc.message, status_code=422) from exc
    except (ContractValidationError, ValueError) as exc:
        raise InternalBoundaryError(
            "RESEARCH_CONTRACT_INVALID",
            str(exc),
            status_code=422,
        ) from exc
