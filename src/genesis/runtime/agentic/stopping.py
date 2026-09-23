"""Deterministic mappings from internal stops to existing canonical semantics."""

from dataclasses import dataclass
from typing import ClassVar, Literal

from genesis.runtime.agentic.models import StopReason


@dataclass(frozen=True, slots=True)
class StopProjection:
    status: Literal["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]
    output_state: Literal["AI_INFERRED", "NEEDS_REVIEW", "BLOCKED"]
    error_code: str | None


class StoppingPolicy:
    _PROJECTIONS: ClassVar[dict[StopReason, StopProjection]] = {
        StopReason.SUCCESS: StopProjection("COMPLETED", "AI_INFERRED", None),
        StopReason.NEEDS_INFO: StopProjection("COMPLETED", "NEEDS_REVIEW", None),
        StopReason.APPROVAL_REQUIRED: StopProjection("COMPLETED", "NEEDS_REVIEW", None),
        StopReason.CANCELLED: StopProjection("CANCELLED", "BLOCKED", "RUNTIME_CANCELLED"),
        StopReason.TIMEOUT: StopProjection("TIMED_OUT", "BLOCKED", "RUNTIME_TIMEOUT"),
        StopReason.TOOL_DENIED: StopProjection("FAILED", "BLOCKED", "TOOL_DENIED"),
        StopReason.TOOL_FAILED: StopProjection("FAILED", "BLOCKED", "TOOL_FAILED"),
        StopReason.MODEL_FAILED: StopProjection("FAILED", "NEEDS_REVIEW", "MODEL_FAILED"),
        StopReason.OUTPUT_INVALID: StopProjection("FAILED", "NEEDS_REVIEW", "OUTPUT_INVALID"),
        StopReason.EVIDENCE_INSUFFICIENT: StopProjection(
            "FAILED", "NEEDS_REVIEW", "EVIDENCE_INSUFFICIENT"
        ),
        StopReason.BUDGET_EXHAUSTED: StopProjection("FAILED", "BLOCKED", "BUDGET_EXHAUSTED"),
        StopReason.MAX_STEPS: StopProjection("FAILED", "BLOCKED", "MAX_STEPS"),
        StopReason.MAX_TOOL_CALLS: StopProjection("FAILED", "BLOCKED", "MAX_TOOL_CALLS"),
        StopReason.DELEGATION_DENIED: StopProjection("FAILED", "BLOCKED", "DELEGATION_DENIED"),
        StopReason.DELEGATION_FAILED: StopProjection("FAILED", "NEEDS_REVIEW", "DELEGATION_FAILED"),
    }

    def project(self, reason: StopReason) -> StopProjection:
        return self._PROJECTIONS[reason]
