"""Minimal single-pass planner for runs that do not require tool orchestration."""

import json
from collections.abc import Mapping
from typing import Any

from genesis.agents.definitions import AgentDefinition
from genesis.runtime.agentic.models import ExecutionPlan


class SinglePassPlanner:
    async def plan(
        self,
        definition: AgentDefinition,
        request: Mapping[str, Any],
    ) -> ExecutionPlan:
        return ExecutionPlan(
            messages=(
                {
                    "role": "system",
                    "content": definition.purpose,
                },
                {
                    "role": "user",
                    "content": json.dumps(request["input"], sort_keys=True),
                },
            )
        )
