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
            "history": [
                {
                    "role": item["role"],
                    "content": str(item["content"])[-1000:],
                    "instruction_authority": False,
                }
                for item in request["input"].get("history", [])[-6:]
                if isinstance(item, dict) and item.get("role") in {"USER", "ASSISTANT"}
            ],
            "tool_selection_mode": request["input"].get("tool_selection_mode", "FIXED"),
            "business_reference": request["input"].get("business_reference"),
            "tool_catalog": [
                item
                for item in request["input"].get("tool_catalog", [])
                if isinstance(item, dict)
                and item.get("tool_id") in request.get("requested_tool_ids", [])
            ],
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
