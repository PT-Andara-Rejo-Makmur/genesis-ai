from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workflow_id: str = Field(min_length=3)
    run_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    state: dict[str, Any]


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    state: dict[str, Any]
    status: str


class OrchestrationEngine(Protocol):
    async def execute(self, request: WorkflowRequest) -> WorkflowResult: ...
