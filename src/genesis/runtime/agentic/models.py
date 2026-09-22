"""Internal, non-authoritative models for bounded agentic execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.orchestration.delegation.models import (
    ChildObservation,
    DelegationIntent,
    DelegationProposal,
)


class ToolCallIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool_id: str = Field(min_length=3, max_length=128)
    arguments: dict[str, Any]


class ExecutionPlan(BaseModel):
    """Legacy one-shot plan retained for compatibility with existing callers."""

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


class AgenticActionKind(StrEnum):
    TOOL = "TOOL"
    DELEGATE = "DELEGATE"
    FINISH = "FINISH"
    NEEDS_INFO = "NEEDS_INFO"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FAIL = "FAIL"


class StopReason(StrEnum):
    SUCCESS = "SUCCESS"
    NEEDS_INFO = "NEEDS_INFO"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    TOOL_DENIED = "TOOL_DENIED"
    TOOL_FAILED = "TOOL_FAILED"
    MODEL_FAILED = "MODEL_FAILED"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    MAX_STEPS = "MAX_STEPS"
    MAX_TOOL_CALLS = "MAX_TOOL_CALLS"
    DELEGATION_DENIED = "DELEGATION_DENIED"
    DELEGATION_FAILED = "DELEGATION_FAILED"


class ModelUsage(BaseModel):
    """Usage reported by a planner that invoked ModelGateway through an adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    route_id: str | None = Field(default=None, min_length=1)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ToolObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    step_index: int = Field(ge=1)
    tool_call_id: str
    tool_id: str
    status: Literal["SUCCESS", "COMPLETED", "FAILED", "TIMEOUT", "DENIED", "REJECTED"]
    output: Any = None
    error_code: str | None = None


class AgenticDecision(BaseModel):
    """Operational next action only; never stores private chain-of-thought."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: AgenticActionKind
    tool_intent: ToolCallIntent | None = None
    delegation_intent: DelegationIntent | None = None
    delegation_proposal: DelegationProposal | None = None
    output: Any = None
    messages: tuple[dict[str, Any], ...] = ()
    reason_code: str | None = Field(default=None, min_length=3, max_length=64)
    safe_message: str | None = Field(default=None, min_length=1, max_length=1_000)
    evidence_ids: tuple[str, ...] = ()
    requires_evidence: bool = False
    planner_usage: ModelUsage | None = None

    @model_validator(mode="after")
    def enforce_action_shape(self) -> AgenticDecision:
        if self.kind is AgenticActionKind.TOOL and self.tool_intent is None:
            raise ValueError("TOOL decision requires tool_intent")
        if self.kind is not AgenticActionKind.TOOL and self.tool_intent is not None:
            raise ValueError("tool_intent is only valid for TOOL decisions")
        if self.kind is AgenticActionKind.DELEGATE and (
            (self.delegation_intent is None) == (self.delegation_proposal is None)
        ):
            raise ValueError("DELEGATE requires exactly one intent or proposal")
        if self.kind is not AgenticActionKind.DELEGATE and self.delegation_intent is not None:
            raise ValueError("delegation_intent is only valid for DELEGATE decisions")
        if self.kind is not AgenticActionKind.DELEGATE and self.delegation_proposal is not None:
            raise ValueError("delegation_proposal is only valid for DELEGATE decisions")
        if self.kind is AgenticActionKind.FINISH and self.output is None and not self.messages:
            raise ValueError("FINISH requires output or model messages")
        if self.kind is AgenticActionKind.FAIL and self.reason_code is None:
            raise ValueError("FAIL decision requires reason_code")
        return self


class AgenticRuntimeState(BaseModel):
    """Bounded operational trajectory. It contains no hidden reasoning text."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    root_run_id: str
    parent_run_id: str | None = None
    correlation_id: str
    goal: str
    input: dict[str, Any]
    step_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    observations: tuple[ToolObservation, ...] = ()
    child_observations: tuple[ChildObservation, ...] = ()
    submitted_delegation_keys: frozenset[str] = frozenset()
    reserved_child_tokens: int = Field(default=0, ge=0)
    reserved_child_cost: float = Field(default=0, ge=0)
    known_evidence_ids: tuple[str, ...] = ()
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    route_ids: tuple[str, ...] = ()
    max_tokens: int
    max_cost: float | None = None

    @property
    def consumed_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.consumed_tokens)


class RuntimeFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        output_state: Literal["BLOCKED", "NEEDS_REVIEW"] = "BLOCKED",
        run_status: Literal["FAILED", "CANCELLED", "TIMED_OUT"] = "FAILED",
        stop_reason: StopReason | None = None,
        state: AgenticRuntimeState | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.output_state = output_state
        self.run_status = run_status
        self.stop_reason = stop_reason
        self.state = state


class RuntimeRequestRejected(ValueError):
    """Raised when the canonical AgentRunRequest itself is malformed."""
