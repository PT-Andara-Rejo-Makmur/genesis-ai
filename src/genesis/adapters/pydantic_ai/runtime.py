"""PydanticAI runtime isolation adapter.

The injected invoker must be configured with a ModelGateway-backed model. Provider-backed
PydanticAI agents are intentionally not constructed here.
"""

from __future__ import annotations

from typing import Any, Protocol

from genesis.agents.definitions import AgentDefinition
from genesis.agents.runtime import AgentRunInput, AgentRunResult


class PydanticAIInvoker(Protocol):
    async def invoke(
        self,
        *,
        definition: AgentDefinition,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> Any: ...


class PydanticAIRuntimeAdapter:
    """Maps the generic runtime contract to a governed PydanticAI invoker."""

    def __init__(self, invoker: PydanticAIInvoker) -> None:
        self._invoker = invoker

    async def run(self, definition: AgentDefinition, run_input: AgentRunInput) -> AgentRunResult:
        output = await self._invoker.invoke(
            definition=definition,
            payload=run_input.payload,
            correlation_id=run_input.correlation_id,
        )
        return AgentRunResult(
            run_id=run_input.run_id,
            output=output,
            output_state="AI_INFERRED",
        )
