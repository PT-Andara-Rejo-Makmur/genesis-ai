"""Deployed model traffic cannot transmit business context or credentials in plaintext."""

import pytest
from pydantic import ValidationError

from genesis.config import Settings


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_public_router_requires_tls(environment: str) -> None:
    with pytest.raises(ValidationError) as failure:
        Settings(
            _env_file=None,
            APP_ENV=environment,
            DEFAULT_MODEL_ROUTE="nine_router",
            NINE_ROUTER_BASE_URL="http://203.0.113.10:20128/v1",
            NINE_ROUTER_API_KEY="secret-test-value",
        )
    assert "requires an HTTPS" in str(failure.value)
    assert "secret-test-value" not in str(failure.value)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_tls_router_is_accepted(environment: str) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV=environment,
        DEFAULT_MODEL_ROUTE="nine_router",
        NINE_ROUTER_BASE_URL="https://router.example/v1",
        NINE_ROUTER_API_KEY="secret-test-value",
    )
    assert settings.production_runtime_enabled


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_router_mock_can_use_http(environment: str) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV=environment,
        DEFAULT_MODEL_ROUTE="nine_router",
        NINE_ROUTER_BASE_URL="http://router.test/v1",
    )
    assert settings.NINE_ROUTER_BASE_URL == "http://router.test/v1"
