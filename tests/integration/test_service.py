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
async def test_internal_system_info_declares_non_authority(client: httpx.AsyncClient) -> None:
    response = await client.get("/internal/v1/system/info")
    assert response.status_code == 200
    assert response.json()["role"] == "AI_CONTROL_PLANE"
    assert response.json()["authoritative_business_state"] is False


@pytest.mark.asyncio
async def test_application_lifespan(settings: Settings) -> None:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert app.state.started is True
    assert app.state.started is False
