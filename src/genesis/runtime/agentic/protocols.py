"""Ports used by AgentRuntimeEngine; framework adapters implement these elsewhere."""

from collections.abc import Mapping
from typing import Any, Protocol

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.agentic.models import ExecutionPlan


class RuntimePlanner(Protocol):
    async def plan(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
    ) -> ExecutionPlan: ...


class ToolBoundaryClient(Protocol):
    async def execute(
        self,
        payload: Mapping[str, Any],
        *,
        correlation_id: str,
    ) -> dict[str, Any]: ...
