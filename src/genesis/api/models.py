from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ready"] = "ready"
    provider_required: bool = False
    backend_configured: bool


class SystemInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: Literal["genesis-ai"] = "genesis-ai"
    version: str
    role: Literal["AI_CONTROL_PLANE"] = "AI_CONTROL_PLANE"
    authoritative_business_state: Literal[False] = False


class IntegrationDiagnosticResponse(BaseModel):
    """Transport projection of the canonical GENESIS diagnostic contract."""

    model_config = ConfigDict(extra="forbid")
    service: Literal["genesis-ai"] = "genesis-ai"
    status: Literal["reachable"] = "reachable"
    role: Literal["AI_CONTROL_PLANE"] = "AI_CONTROL_PLANE"
    authoritative_business_state: Literal[False] = False
    provider_required: Literal[False] = False
    correlation_id: str
