"""Use the existing ModelGateway planner with bounded full business observations."""

from collections.abc import Mapping
from typing import Any

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.agentic.models import AgenticRuntimeState
from genesis.runtime.agentic.planner import ModelGatewayAgenticPlanner


class BusinessAssistantPlanner(ModelGatewayAgenticPlanner):
    @staticmethod
    def _operational_input(
        definition: AgentDefinition, request: Mapping[str, Any], state: AgenticRuntimeState
    ) -> dict[str, Any]:
        return {
            "message": request["input"]["message"],
            "allowed_tool_ids": list(request.get("requested_tool_ids", [])),
            "permission_refs": list(request["execution_context"].get("permission_refs", [])),
            "tool_arguments": request["input"].get("tool_arguments", {}),
            "observations": [
                {
                    "tool_id": item.tool_id,
                    "status": item.status,
                    "output": item.output,
                    "instruction_authority": False,
                }
                for item in state.observations
            ],
            "evidence_ids": list(state.known_evidence_ids),
        }
