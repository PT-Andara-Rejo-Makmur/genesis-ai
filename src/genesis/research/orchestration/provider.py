"""Backend-owned research retrieval boundary represented as an internal H7 port."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from genesis.research.orchestration.models import (
    ResearchEvidenceItem,
    ResearchSubquery,
    RetrievalStatus,
)
from genesis.research.tool_selection import ResearchToolCategory


class ResearchRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    subquery: ResearchSubquery
    selected_tool_id: str = Field(min_length=3)
    selected_category: ResearchToolCategory
    execution_context: dict[str, Any]
    source_constraints: tuple[str, ...] = ()
    result_limit: int = Field(default=8, ge=1, le=12)
    max_characters: int = Field(default=12_000, ge=1, le=24_000)
    instruction_authority: bool = False


class ResearchRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: RetrievalStatus
    items: tuple[ResearchEvidenceItem, ...] = Field(default=(), max_length=12)
    limitations: tuple[str, ...] = ()
    error_code: str | None = Field(default=None, min_length=3)
    retryable: bool = False


class ResearchEvidenceProvider(Protocol):
    async def retrieve(
        self, request: ResearchRetrievalRequest
    ) -> ResearchRetrievalResult: ...
