"""Framework-neutral models for one bounded Agent runtime execution."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool_id: str = Field(min_length=3, max_length=128)
    arguments: dict[str, Any]


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    messages: tuple[dict[str, Any], ...] = Field(min_length=1)
    tool_calls: tuple[ToolCallIntent, ...] = ()


class RuntimeAuthorization(BaseModel):
    """Backend-issued execution snapshot; it grants no new authority in GENESIS."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3, max_length=128)
    registry_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    lifecycle_state: Literal["ACTIVE", "TEST_AUTHORIZED"]
    allowed_tool_ids: tuple[str, ...] = ()


class RuntimeFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        output_state: Literal["BLOCKED", "NEEDS_REVIEW"] = "BLOCKED",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.output_state = output_state


class RuntimeRequestRejected(ValueError):
    """Raised when the canonical AgentRunRequest itself is malformed."""
