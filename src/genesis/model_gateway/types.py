from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from genesis.runtime.limits import ExecutionBudget


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    policy_ref: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    messages: tuple[dict[str, Any], ...] = Field(min_length=1)
    requested_max_tokens: int = Field(ge=1)
    budget: ExecutionBudget


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str
    route_id: str
    provider_request_id: str | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float | None = Field(default=None, ge=0)
