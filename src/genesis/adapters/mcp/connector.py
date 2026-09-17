"""MCP interoperability behind the governed ALOS tool boundary."""

from __future__ import annotations

from typing import Any, Protocol


class MCPConnector(Protocol):
    async def describe_tool(self, tool_name: str) -> dict[str, Any]: ...


class GovernedMCPAdapter:
    """Produces ToolRequest arguments; never performs authoritative business actions."""

    def __init__(self, connector: MCPConnector) -> None:
        self._connector = connector

    async def prepare_tool_request(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        description = await self._connector.describe_tool(tool_name)
        return {
            "connector": "mcp",
            "tool_name": tool_name,
            "arguments": arguments,
            "connector_metadata": description,
        }
