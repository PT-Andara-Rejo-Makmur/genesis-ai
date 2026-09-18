"""Non-production ToolRequest fixture for governed integration verification."""

from datetime import UTC, datetime
from typing import Any


def diagnostic_echo_request(
    *,
    correlation_id: str,
    message: str,
    tool_call_id: str = "toolcall_diagnostic_echo_001",
    run_id: str = "run_diagnostic_001",
) -> dict[str, Any]:
    """Create contract-shaped data only; execution remains in ALOS Backend."""

    return {
        "tool_call_id": tool_call_id,
        "run_id": run_id,
        "tool_id": "diagnostic.echo",
        "execution_context": {
            "tenant_id": "tenant_diagnostic_001",
            "organization_id": "org_diagnostic_001",
            "workspace_id": "workspace_diagnostic_001",
            "actor_id": "actor_diagnostic_001",
            "authority_context": {"role": "diagnostic_runner", "authority_level": "SYSTEM"},
            "permission_refs": ["tools.diagnostic.execute"],
            "scope_refs": ["scope.diagnostic"],
            "data_classification": "INTERNAL",
            "correlation_id": correlation_id,
        },
        "arguments": {"message": message},
        "requested_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
