import hashlib
import json
from typing import Any, cast

from fastapi import APIRouter, Depends, Request

from genesis import __version__
from genesis.agents.definitions import AgentDefinition
from genesis.api.auth import verify_service_token
from genesis.api.errors import InternalBoundaryError
from genesis.api.integration import DeterministicResearchGateway, run_deterministic_invocation
from genesis.api.models import HealthResponse, IntegrationDiagnosticResponse, SystemInfoResponse
from genesis.config import Settings
from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.control_plane.factory import (
    CapabilityFactory,
    FactoryAnalysisRequest,
    FactoryAnalysisResult,
)
from genesis.evals import (
    CORE_AI_ASSURANCE_REGRESSION_SET,
    DeterministicReadinessPolicy,
    EvaluationRunner,
    EvaluationSubjectSnapshot,
)
from genesis.observability.correlation import current_correlation_id
from genesis.research import (
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchDecisionFailure,
    ResearchDecisionRequest,
    ResearchRisk,
)
from genesis.research.engine import ResearchEngine, ResearchOutputInvalid
from genesis.reviews import (
    ReviewPackageAssembler,
    ReviewSubjectSnapshot,
    RiskEvidenceSummaryBuilder,
)
from genesis.runtime.agentic import RuntimeAuthorization, RuntimeRequestRejected

RUNTIME_INVOCATION_SCHEMA = (
    "https://schemas.alos.dev/v1/runtime/agent-runtime-invocation.schema.json"
)
REVIEW_INVOCATION_SCHEMA = "https://schemas.alos.dev/v1/review/review-invocation.schema.json"

RESEARCH_ANALYSIS_REQUEST_SCHEMA = (
    "https://schemas.alos.dev/v1/research/research-analysis-request.schema.json"
)

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_service_token)],
)


def _catalog(settings: Settings) -> CanonicalContractCatalog:
    if settings.ALOS_CONTRACTS_PATH is None:
        raise InternalBoundaryError(
            "CONTRACT_CATALOG_NOT_CONFIGURED",
            "ALOS_CONTRACTS_PATH is required for canonical contract validation.",
            status_code=503,
        )
    return CanonicalContractCatalog(settings.ALOS_CONTRACTS_PATH)


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


@router.post("/agent-runs")
async def execute_agent_run(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Validate one Backend-issued envelope and delegate execution to AgentRuntimeEngine."""

    settings: Settings = request.app.state.settings
    correlation_id = current_correlation_id()
    try:
        contracts = _catalog(settings)
        invocation = contracts.validate(RUNTIME_INVOCATION_SCHEMA, payload)
        run_request = cast(dict[str, Any], invocation["run_request"])
        context = cast(dict[str, Any], run_request["execution_context"])
        if context["correlation_id"] != correlation_id:
            raise InternalBoundaryError(
                "CORRELATION_ID_MISMATCH",
                "Payload correlation_id must match X-Correlation-ID.",
                status_code=422,
            )
        authorization = RuntimeAuthorization.model_validate(invocation["runtime_authorization"])
        definition_payload = cast(dict[str, Any], invocation["agent_definition"])
        definition_digest = hashlib.sha256(
            json.dumps(definition_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if authorization.registry_digest != definition_digest:
            raise InternalBoundaryError(
                "REGISTRY_DIGEST_MISMATCH",
                "Runtime authorization does not match the immutable Agent definition.",
                status_code=422,
            )
        definition = AgentDefinition.from_canonical_payload(definition_payload, contracts=contracts)
        requested_tools = set(cast(list[str], run_request.get("requested_tool_ids", [])))
        if not requested_tools.issubset(definition.tool_ids) or not requested_tools.issubset(
            authorization.allowed_tool_ids
        ):
            raise InternalBoundaryError(
                "TOOL_NOT_AUTHORIZED",
                (
                    "Requested tools must remain within the exact definition "
                    "and Backend authorization."
                ),
                status_code=422,
            )
        if authorization.run_id != run_request["run_id"]:
            raise InternalBoundaryError(
                "RUN_AUTHORIZATION_MISMATCH",
                "Runtime authorization must identify the canonical run request.",
                status_code=422,
            )
        if run_request.get("execution_mode") != "TEST" or not settings.test_runtime_enabled:
            raise InternalBoundaryError(
                "MODEL_ROUTE_NOT_CONFIGURED",
                "Only the explicitly enabled deterministic TEST runtime is configured.",
                status_code=503,
            )
        return await run_deterministic_invocation(
            settings=settings,
            contracts=contracts,
            definition=definition,
            run_request=run_request,
            authorization=authorization,
            http_client=getattr(request.app.state, "backend_http_client", None),
        )
    except InternalBoundaryError:
        raise
    except (ContractValidationError, RuntimeRequestRejected, ValueError) as exc:
        raise InternalBoundaryError(
            "RUNTIME_INVOCATION_INVALID", str(exc), status_code=422
        ) from exc


@router.post("/reviews")
async def assemble_review_package(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Assemble advisory evidence; this boundary cannot approve or release anything."""

    settings: Settings = request.app.state.settings
    try:
        canonical = _catalog(settings).validate(REVIEW_INVOCATION_SCHEMA, payload)
        subject = ReviewSubjectSnapshot.model_validate(canonical.get("subject"))
        evaluation_subject = EvaluationSubjectSnapshot.model_validate(
            canonical.get("evaluation_subject")
        )
        if subject.correlation_id != current_correlation_id():
            raise InternalBoundaryError(
                "CORRELATION_ID_MISMATCH",
                "Review correlation_id must match X-Correlation-ID.",
                status_code=422,
            )
        if (
            evaluation_subject.subject_id != subject.subject_id
            or evaluation_subject.subject_version != subject.subject_version
            or evaluation_subject.tenant_id != subject.tenant_id
            or evaluation_subject.organization_id != subject.organization_id
            or evaluation_subject.workspace_id != subject.workspace_id
            or evaluation_subject.correlation_id != subject.correlation_id
        ):
            raise InternalBoundaryError(
                "REVIEW_SUBJECT_MISMATCH",
                "Evaluation facts must identify the exact review subject snapshot.",
                status_code=422,
            )
        suite = EvaluationRunner.for_regression_set(CORE_AI_ASSURANCE_REGRESSION_SET).run(
            CORE_AI_ASSURANCE_REGRESSION_SET, evaluation_subject
        )
        readiness = DeterministicReadinessPolicy().assess_against(
            CORE_AI_ASSURANCE_REGRESSION_SET, suite
        )
        summary = RiskEvidenceSummaryBuilder().build(suite, readiness)
        return ReviewPackageAssembler(contracts=_catalog(settings)).assemble(
            subject=subject, suite=suite, summary=summary
        )
    except InternalBoundaryError:
        raise
    except (ContractValidationError, ValueError) as exc:
        raise InternalBoundaryError("REVIEW_PACKAGE_INVALID", str(exc), status_code=422) from exc


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


@router.post("/research/run")
async def run_deterministic_research(
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Exercise canonical research reasoning with a deterministic TEST ModelGateway."""

    settings: Settings = request.app.state.settings
    if not settings.ENABLE_TEST_RUNTIME or settings.APP_ENV not in {"development", "test"}:
        raise InternalBoundaryError(
            "TEST_RUNTIME_DISABLED",
            "Deterministic research runtime is disabled.",
            status_code=403,
        )
    correlation_id = current_correlation_id()
    if payload.get("correlation_id") != correlation_id:
        raise InternalBoundaryError(
            "CORRELATION_ID_MISMATCH",
            "Payload correlation_id must match X-Correlation-ID.",
            status_code=422,
        )
    context = payload.get("context_bundle")
    evidence_refs = context.get("evidence_refs", []) if isinstance(context, dict) else []
    if len(evidence_refs) != 1 or not isinstance(evidence_refs[0], dict):
        raise InternalBoundaryError(
            "RESEARCH_EVIDENCE_REQUIRED",
            "Deterministic research requires one Backend-issued evidence reference.",
            status_code=422,
        )
    try:
        engine = ResearchEngine(
            contracts=_catalog(settings),
            model_gateway=DeterministicResearchGateway(
                evidence_id=str(evidence_refs[0]["evidence_id"]),
                domain=str(payload.get("domain", "TECHNOLOGY")),
            ),
        )
        return await engine.research(payload)
    except (ContractValidationError, ResearchOutputInvalid, KeyError, ValueError) as exc:
        raise InternalBoundaryError(
            "RESEARCH_CONTRACT_INVALID",
            str(exc),
            status_code=422,
        ) from exc
