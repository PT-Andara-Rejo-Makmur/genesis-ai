"""Ports used by AgentRuntimeEngine; adapters implement authority elsewhere."""

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.agentic.models import (
    AgenticDecision,
    AgenticRuntimeState,
    StopReason,
)


@runtime_checkable
class AgenticPlanner(Protocol):
    """Iterative decision port; any ModelGateway usage must be reported in the decision."""

    async def next_action(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
        state: AgenticRuntimeState,
    ) -> AgenticDecision: ...


class ToolBoundaryClient(Protocol):
    async def execute(
        self,
        payload: Mapping[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]: ...


class CancellationProbe(Protocol):
    async def is_cancelled(self, run_id: str) -> bool: ...


class RuntimeObserver(Protocol):
    def on_step_started(self, state: AgenticRuntimeState) -> None: ...

    def on_tool_requested(self, tool_call_id: str, tool_id: str, step_index: int) -> None: ...

    def on_tool_result(self, tool_call_id: str, status: str, step_index: int) -> None: ...

    def on_stop(self, reason: StopReason, state: AgenticRuntimeState) -> None: ...
