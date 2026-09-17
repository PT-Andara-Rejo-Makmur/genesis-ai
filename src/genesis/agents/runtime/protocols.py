from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.limits import ExecutionBudget


class AgentRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3)
    root_run_id: str = Field(min_length=3)
    parent_run_id: str | None = None
    tenant_id: str = Field(min_length=3)
    workspace_id: str = Field(min_length=3)
    correlation_id: str = Field(min_length=3)
    payload: dict[str, Any]
    budget: ExecutionBudget


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    output: Any
    output_state: str
    evidence_refs: tuple[str, ...] = ()


class AgentRuntime(Protocol):
    async def run(
        self, definition: AgentDefinition, run_input: AgentRunInput
    ) -> AgentRunResult: ...
