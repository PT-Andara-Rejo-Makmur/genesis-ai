import httpx
import pytest


def _payload(correlation_id: str, *, source_mode: str) -> dict[str, object]:
    return {
        "question": "Apa teknologi yang relevan untuk otomasi operasional?",
        "source_mode": source_mode,
        "domain": "TECHNOLOGY",
        "execution_context": {
            "tenant_id": "tenant_research",
            "organization_id": "org_research",
            "workspace_id": "workspace_research",
            "actor_id": "actor_research",
            "authority_context": {
                "role": "DIVISION_MEMBER",
                "role_refs": ["DIVISION_MEMBER"],
                "authority_level": "REQUESTER",
            },
            "permission_refs": ["research.request", "research.external.read"],
            "allowed_tool_ids": ["research.external.retrieve"],
            "scope_refs": ["research.technology", "scope.sources.external_read"],
            "data_classification": "INTERNAL",
            "correlation_id": correlation_id,
            "execution_budget": {
                "max_cost": 0,
                "max_tool_calls": 1,
                "timeout_seconds": 30,
            },
        },
    }


@pytest.mark.asyncio
async def test_external_research_returns_backend_retrieval_proposal(
    client: httpx.AsyncClient,
) -> None:
    correlation_id = "corr_genesis_research_external_001"
    response = await client.post(
        "/internal/v1/research",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
        json=_payload(correlation_id, source_mode="EXTERNAL"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == correlation_id
    assert body["decision"] == "REQUEST_EXTERNAL_RESEARCH"
    assert body["retrieval"] == {
        "boundary": "BACKEND_TOOL_EXECUTOR",
        "tool_id": "research.external.retrieve",
        "instruction_authority": False,
        "permission_expansion": False,
        "scope_expansion": False,
    }
    assert body["external_content_trust"] == "UNTRUSTED"


@pytest.mark.asyncio
async def test_internal_only_research_does_not_request_external_tool(
    client: httpx.AsyncClient,
) -> None:
    correlation_id = "corr_genesis_research_internal_001"
    response = await client.post(
        "/internal/v1/research",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": correlation_id,
        },
        json=_payload(correlation_id, source_mode="INTERNAL"),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "INSUFFICIENT_EVIDENCE"
    assert response.json()["retrieval"] is None


@pytest.mark.asyncio
async def test_research_boundary_rejects_correlation_mismatch(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/internal/v1/research",
        headers={
            "Authorization": "Bearer test-only-token",
            "X-Correlation-ID": "corr_header_research_001",
        },
        json=_payload("corr_payload_research_001", source_mode="EXTERNAL"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "CORRELATION_ID_MISMATCH"
    assert response.json()["correlation_id"] == "corr_header_research_001"
