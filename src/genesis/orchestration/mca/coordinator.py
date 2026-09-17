from genesis.orchestration.workflows import (
    OrchestrationEngine,
    WorkflowRequest,
    WorkflowResult,
)


class MasterCoordinator:
    """The single MCA business orchestrator. It does not manage workforce lifecycle."""

    def __init__(self, orchestration: OrchestrationEngine) -> None:
        self._orchestration = orchestration

    async def coordinate(self, request: WorkflowRequest) -> WorkflowResult:
        return await self._orchestration.execute(request)
