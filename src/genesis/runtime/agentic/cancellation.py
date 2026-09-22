"""Non-authoritative cancellation and trace defaults for H5 AI."""

from genesis.runtime.agentic.models import AgenticRuntimeState, StopReason


class NeverCancelled:
    async def is_cancelled(self, run_id: str) -> bool:
        del run_id
        return False


class NullRuntimeObserver:
    def on_step_started(self, state: AgenticRuntimeState) -> None:
        del state

    def on_tool_requested(self, tool_call_id: str, tool_id: str, step_index: int) -> None:
        del tool_call_id, tool_id, step_index

    def on_tool_result(self, tool_call_id: str, status: str, step_index: int) -> None:
        del tool_call_id, status, step_index

    def on_stop(self, reason: StopReason, state: AgenticRuntimeState) -> None:
        del reason, state
