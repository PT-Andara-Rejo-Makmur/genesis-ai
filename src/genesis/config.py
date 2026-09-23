"""Typed GENESIS service configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
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
    MAX_DELEGATION_DEPTH: int = Field(default=3, ge=0, le=20)
    MAX_DELEGATION_CHILDREN: int = Field(default=8, ge=0, le=100)

    @property
    def test_runtime_enabled(self) -> bool:
        return self.ENABLE_TEST_RUNTIME and self.APP_ENV in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
