"""LangGraph isolation adapter for stateful workflows, pause/resume, and recovery."""

from __future__ import annotations

from typing import Any, Protocol

from genesis.orchestration.workflows import WorkflowRequest, WorkflowResult


class CompiledLangGraph(Protocol):
    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]: ...


class LangGraphOrchestrationAdapter:
    def __init__(self, graphs: dict[str, CompiledLangGraph]) -> None:
        self._graphs = graphs

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        graph = self._graphs.get(request.workflow_id)
        if graph is None:
            raise KeyError(f"Unknown workflow: {request.workflow_id}")
        state = await graph.ainvoke(dict(request.state))
        return WorkflowResult(run_id=request.run_id, state=state, status="COMPLETED")
