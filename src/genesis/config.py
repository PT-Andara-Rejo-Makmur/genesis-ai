"""Typed GENESIS service configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        hide_input_in_errors=True,
    )

    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = Field(default=8100, ge=1, le=65535)
    ALOS_BACKEND_BASE_URL: str = "http://localhost:8000"
    ALOS_INTERNAL_TOKEN: SecretStr = SecretStr("")
    ALOS_CONTRACTS_PATH: Path | None = None
    OTEL_SERVICE_NAME: str = "genesis-ai"
    DEFAULT_MODEL_ROUTE: str = "disabled"
    ENABLE_TEST_RUNTIME: bool = False
    NINE_ROUTER_BASE_URL: str = ""
    NINE_ROUTER_API_KEY: SecretStr = Field(default=SecretStr(""), repr=False)
    NINE_ROUTER_TIMEOUT_SECONDS: float = Field(default=10, gt=0, le=120)
    NINE_ROUTER_MODEL_DEFAULT: str = ""
    NINE_ROUTER_MODEL_FAST: str = ""
    NINE_ROUTER_MODEL_STANDARD: str = ""
    NINE_ROUTER_MODEL_REASONING: str = ""
    NINE_ROUTER_MODEL_CODING: str = ""
    NINE_ROUTER_MODEL_CRITICAL: str = ""
    NINE_ROUTER_MAXIMUM_CLASSIFICATION: Literal[
        "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"
    ] = "INTERNAL"
    MAX_DELEGATION_DEPTH: int = Field(default=3, ge=0, le=20)
    MAX_DELEGATION_CHILDREN: int = Field(default=8, ge=0, le=100)

    @field_validator("NINE_ROUTER_BASE_URL")
    @classmethod
    def validate_router_url(cls, value: str) -> str:
        if not value.strip():
            return ""
        url = TypeAdapter(AnyHttpUrl).validate_python(value.strip())
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Router base URL must not contain credentials, query, or fragment")
        return str(url).rstrip("/")

    @model_validator(mode="after")
    def require_deployed_router_tls(self) -> Self:
        if (
            self.APP_ENV in {"staging", "production"}
            and self.production_runtime_enabled
            and self.NINE_ROUTER_BASE_URL
            and not self.NINE_ROUTER_BASE_URL.startswith("https://")
        ):
            raise ValueError("Staging/production model traffic requires an HTTPS router endpoint")
        return self

    @property
    def production_runtime_enabled(self) -> bool:
        return self.DEFAULT_MODEL_ROUTE == "nine_router"

    @property
    def test_runtime_enabled(self) -> bool:
        return self.ENABLE_TEST_RUNTIME and self.APP_ENV in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
