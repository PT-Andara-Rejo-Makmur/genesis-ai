import httpx
import pytest

from genesis.config import Settings
from genesis.main import create_app


@pytest.mark.asyncio
async def test_health_and_readiness(client: httpx.AsyncClient) -> None:
    health = await client.get("/health", headers={"X-Correlation-ID": "corr_health_001"})
    ready = await client.get("/ready")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert health.headers["X-Correlation-ID"] == "corr_health_001"
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "provider_required": False,
        "backend_configured": True,
    }


@pytest.mark.asyncio
async def test_internal_health_requires_service_token(client: httpx.AsyncClient) -> None:
    correlation_id = "corr_internal_health_001"
    response = await client.get(
        "/internal/v1/health",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"] == correlation_id


@pytest.mark.asyncio
async def test_internal_system_info_declares_non_authority(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/internal/v1/system/info",
        headers={"Authorization": "Bearer test-only-token"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "AI_CONTROL_PLANE"
    assert response.json()["authoritative_business_state"] is False


@pytest.mark.asyncio
async def test_integration_diagnostic_propagates_correlation(client: httpx.AsyncClient) -> None:
    correlation_id = "corr_genesis_diagnostic_001"
    response = await client.get(
        "/internal/v1/system/integration",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.json() == {
        "service": "genesis-ai",
        "status": "reachable",
        "role": "AI_CONTROL_PLANE",
        "authoritative_business_state": False,
        "provider_required": False,
        "correlation_id": correlation_id,
    }


@pytest.mark.asyncio
async def test_internal_endpoint_rejects_missing_service_token(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        "/internal/v1/system/integration",
        headers={"X-Correlation-ID": "corr_auth_denied_001"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "INTERNAL_AUTH_DENIED",
        "message": "GENESIS internal service authentication failed.",
        "correlation_id": "corr_auth_denied_001",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_factory_endpoint_returns_draft_without_authoritative_write(
    client: httpx.AsyncClient,
) -> None:
    correlation_id = "corr_factory_api_001"
    response = await client.post(
        "/internal/v1/factory/analyze",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
        json={
            "requirement": {
                "execution_context": {
                    "tenant_id": "tenant_api",
                    "organization_id": "organization_api",
                    "workspace_id": "workspace_api",
                    "actor_id": "actor_api",
                    "authority_context": {
                        "role": "REQUESTER",
                        "authority_level": "REQUESTER",
                    },
                    "correlation_id": correlation_id,
                    "scope_refs": ["scope.workspace"],
                    "permission_refs": ["document.read"],
                    "data_classification": "INTERNAL",
                },
                "statement": "Rancang agent untuk menganalisis dokumen internal secara aman",
            },
            "capability_catalog": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["correlation_id"] == correlation_id
    assert payload["agent_draft"]["lifecycle_state"] == "DRAFT"
    assert payload["capability_draft"]["lifecycle_state"] == "DRAFT"
    assert payload["handoff"]["authoritative_state_changed"] is False
    assert payload["handoff"]["target_service"] == "alos-backend"


@pytest.mark.asyncio
async def test_factory_endpoint_rejects_correlation_mismatch(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/internal/v1/factory/analyze",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": "corr_header_001",
        },
        json={
            "requirement": {
                "execution_context": {
                    "tenant_id": "tenant_api",
                    "organization_id": "organization_api",
                    "workspace_id": "workspace_api",
                    "actor_id": "actor_api",
                    "authority_context": {
                        "role": "REQUESTER",
                        "authority_level": "REQUESTER",
                    },
                    "correlation_id": "corr_payload_001",
                    "scope_refs": ["scope.workspace"],
                    "data_classification": "INTERNAL",
                },
                "statement": "Rancang capability untuk menganalisis dokumen secara aman",
            },
            "capability_catalog": [],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "CORRELATION_ID_MISMATCH",
        "message": "Payload correlation_id must match X-Correlation-ID.",
        "correlation_id": "corr_header_001",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_factory_endpoint_returns_structured_error_for_invalid_context(
    client: httpx.AsyncClient,
) -> None:
    correlation_id = "corr_invalid_factory_context_001"
    response = await client.post(
        "/internal/v1/factory/analyze",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
        json={
            "requirement": {
                "execution_context": {
                    "tenant_id": "tenant_api",
                    "organization_id": "organization_api",
                    "workspace_id": "workspace_api",
                    "actor_id": "actor_api",
                    "correlation_id": correlation_id,
                    "scope_refs": ["scope.workspace"],
                    "data_classification": "INTERNAL",
                },
                "statement": "Rancang capability untuk menganalisis dokumen secara aman",
            },
            "capability_catalog": [],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "REQUEST_VALIDATION_FAILED"
    assert payload["correlation_id"] == correlation_id
    assert payload["retryable"] is False
    assert payload["details"]["errors"]


@pytest.mark.asyncio
async def test_application_lifespan(settings: Settings) -> None:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert app.state.started is True
    assert app.state.started is False
