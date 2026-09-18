from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from genesis.runtime.execution import (
    BackendToolClient,
    ToolBoundaryContracts,
    diagnostic_echo_request,
)

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


@pytest.mark.asyncio
async def test_genesis_sends_canonical_tool_request_and_accepts_tool_result() -> None:
    correlation_id = "corr_genesis_tool_001"
    contracts = ToolBoundaryContracts(CONTRACTS_ROOT)
    request_payload = diagnostic_echo_request(
        correlation_id=correlation_id,
        message="governed execution",
    )
    seen_path: str | None = None
    seen_correlation: str | None = None
    seen_token: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path, seen_correlation, seen_token
        seen_path = request.url.path
        seen_correlation = request.headers.get("X-Correlation-ID")
        seen_token = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={
                "tool_call_id": "toolcall_diagnostic_echo_001",
                "run_id": "run_diagnostic_001",
                "tool_id": "diagnostic.echo",
                "correlation_id": correlation_id,
                "status": "SUCCESS",
                "output": {
                    "echo": {"message": "governed execution"},
                    "label": "NON-PRODUCTION TEST TOOL",
                },
                "completed_at": "2026-09-17T08:00:01Z",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://backend.test"
    ) as http:
        client = BackendToolClient(
            base_url="http://backend.test",
            internal_token=SecretStr("test-only-token"),
            contracts=contracts,
            client=http,
        )
        result = await client.execute(request_payload, correlation_id=correlation_id)

    assert seen_path == "/internal/v1/tool-requests"
    assert seen_correlation == correlation_id
    assert seen_token == "Bearer test-only-token"  # noqa: S105
    assert result["status"] == "SUCCESS"
    assert result["correlation_id"] == correlation_id


def test_diagnostic_request_is_valid_contract_data_without_adapter() -> None:
    contracts = ToolBoundaryContracts(CONTRACTS_ROOT)
    payload = diagnostic_echo_request(
        correlation_id="corr_contract_only_001",
        message="contract only",
    )

    contracts.validate_request(payload)
    assert payload["tool_id"] == "diagnostic.echo"
