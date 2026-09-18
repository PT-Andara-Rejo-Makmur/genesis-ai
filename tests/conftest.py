from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from genesis.config import Settings
from genesis.main import create_app

CONTRACTS_ROOT = Path(__file__).resolve().parents[2] / "alos-contracts"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        ALOS_BACKEND_BASE_URL="http://alos-backend.test",
        ALOS_INTERNAL_TOKEN="test-only-token",  # noqa: S106
        ALOS_CONTRACTS_PATH=CONTRACTS_ROOT,
        DEFAULT_MODEL_ROUTE="disabled",
    )


@pytest_asyncio.fixture()
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
