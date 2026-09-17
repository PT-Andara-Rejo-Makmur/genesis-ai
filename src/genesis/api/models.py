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
