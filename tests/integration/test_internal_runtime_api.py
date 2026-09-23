from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from genesis.config import Settings
from genesis.main import create_app

WORKSPACE = Path(__file__).resolve().parents[3]
CONTRACTS_ROOT = WORKSPACE / "alos-contracts"


def invocation() -> dict:
    document = json.loads(
        (CONTRACTS_ROOT / "examples/runtime/agent-runtime-invocation.json").read_text(
            encoding="utf-8"
        )
    )
    document.pop("$schema")
    document["runtime_authorization"]["registry_digest"] = hashlib.sha256(
        json.dumps(document["agent_definition"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return document


def backend_transport(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path.endswith("/cancellation"):
        return httpx.Response(
            200,
            json={
                "run_id": "run_runtime_integration_001",
                "status": "RUNNING",
                "cancellation_state": "NONE",
            },
        )
    assert request.url.path == "/internal/v1/tool-requests"
    payload = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "tool_call_id": payload["tool_call_id"],
            "run_id": payload["run_id"],
            "tool_id": payload["tool_id"],
            "correlation_id": payload["execution_context"]["correlation_id"],
            "status": "SUCCESS",
            "output": {"echo": payload["arguments"]},
            "completed_at": "2026-09-23T10:00:01Z",
        },
    )


@pytest.fixture
async def client() -> httpx.AsyncClient:
    app = create_app(
        Settings(
            _env_file=None,
            APP_ENV="test",
            ALOS_BACKEND_BASE_URL="http://backend.test",
            ALOS_INTERNAL_TOKEN="integration-token",  # noqa: S106
            ALOS_CONTRACTS_PATH=CONTRACTS_ROOT,
            ENABLE_TEST_RUNTIME=True,
        )
    )
    backend = httpx.AsyncClient(
        transport=httpx.MockTransport(backend_transport), base_url="http://backend.test"
    )
    app.state.backend_http_client = backend
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://genesis.test"
    ) as api:
        yield api
    await backend.aclose()


def headers(correlation_id: str = "corr_runtime_integration_001") -> dict[str, str]:
    return {
        "Authorization": "Bearer integration-token",
        "X-Correlation-ID": correlation_id,
    }


@pytest.mark.asyncio
async def test_runtime_endpoint_executes_real_backend_tool_roundtrip(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/internal/v1/agent-runs", headers=headers(), json=invocation())
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "COMPLETED"
    assert result["correlation_id"] == "corr_runtime_integration_001"
    assert result["tool_results"][0]["status"] == "SUCCESS"
    assert result["usage"]["input_tokens"] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["correlation", "digest", "lifecycle", "tool"])
async def test_runtime_endpoint_fails_closed_on_authority_tampering(
    client: httpx.AsyncClient,
    mutation: str,
) -> None:
    payload = deepcopy(invocation())
    request_headers = headers()
    if mutation == "correlation":
        request_headers = headers("corr_wrong_001")
    elif mutation == "digest":
        payload["runtime_authorization"]["registry_digest"] = "b" * 64
    elif mutation == "lifecycle":
        payload["runtime_authorization"]["lifecycle_state"] = "SUSPENDED"
    else:
        payload["runtime_authorization"]["allowed_tool_ids"] = []
    response = await client.post("/internal/v1/agent-runs", headers=request_headers, json=payload)
    if mutation == "tool":
        assert response.status_code == 422
        assert response.json()["code"] == "TOOL_NOT_AUTHORIZED"
    else:
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_review_endpoint_runs_deterministic_assurance_and_remains_advisory(
    client: httpx.AsyncClient,
) -> None:
    evidence = {
        "tenant_id": "tenant_integration_001",
        "organization_id": "org_integration_001",
        "workspace_id": "workspace_integration_001",
        "correlation_id": "corr_runtime_integration_001",
        "scope_refs": ["scope.diagnostic"],
        "evidence_id": "evidence.integration.review",
        "source_id": "source.integration.review",
        "uri": "urn:alos:integration:evidence",
        "captured_at": "2026-09-23T10:00:00Z",
        "content_hash": "sha256:" + "b" * 64,
        "data_classification": "INTERNAL",
        "validation_status": "VALID",
    }
    response = await client.post(
        "/internal/v1/reviews",
        headers=headers(),
        json={
            "subject": {
                "review_id": "review.integration.001",
                "subject_id": "agent.runtime.diagnostic",
                "subject_version": "1.0.0",
                "tenant_id": "tenant_integration_001",
                "organization_id": "org_integration_001",
                "workspace_id": "workspace_integration_001",
                "correlation_id": "corr_runtime_integration_001",
                "purpose": "Provide advisory assurance before human governance.",
                "materiality": "NON_MATERIAL",
                "business_context": {"domain": "TECHNOLOGY"},
                "capability": {
                    "capability_id": "capability.runtime.diagnostic",
                    "version": "1.0.0",
                    "name": "Runtime Diagnostic",
                    "purpose": "Validate governed integration.",
                    "owner": "actor.integration",
                    "capability_type": "AGENT",
                    "output_state": "NEEDS_REVIEW",
                    "lifecycle_state": "DRAFT",
                    "scope_refs": ["scope.diagnostic"],
                },
                "scope": ["scope.diagnostic"],
                "permissions": ["tools.diagnostic.execute"],
                "skills": [],
                "tools": [],
                "model_policy": {
                    "gateway_required": True,
                    "policy_ref": "policy.runtime-test",
                },
                "delegation_policy": {
                    "enabled": False,
                    "lineage_required": True,
                    "max_depth": 0,
                },
                "execution_budget": {"max_tokens": 100, "max_steps": 3},
                "evidence_refs": [evidence],
            },
            "evaluation_subject": {
                "subject_id": "agent.runtime.diagnostic",
                "subject_version": "1.0.0",
                "tenant_id": "tenant_integration_001",
                "organization_id": "org_integration_001",
                "workspace_id": "workspace_integration_001",
                "correlation_id": "corr_runtime_integration_001",
                "observations": {},
            },
        },
    )
    assert response.status_code == 200, response.text
    package = response.json()
    assert package["automated_qa"]["status"] == "FAIL"
    assert "it_decision" not in package
    assert "director_decision" not in package


@pytest.mark.asyncio
async def test_research_endpoint_returns_canonical_evidence_bound_result(
    client: httpx.AsyncClient,
) -> None:
    evidence = {
        "tenant_id": "tenant_integration_001",
        "organization_id": "org_integration_001",
        "workspace_id": "workspace_integration_001",
        "evidence_id": "evidence.integration.research",
        "source_id": "source.integration.research",
        "uri": "urn:alos:integration:research",
        "captured_at": "2026-09-23T10:00:00Z",
        "content_hash": "sha256:" + "c" * 64,
        "source_version": "1.0.0",
        "anchor": "integration-fixture",
        "excerpt": "Authorized research evidence.",
        "data_classification": "INTERNAL",
        "validation_status": "VALID",
    }
    context = {
        "context_id": "context.integration.research",
        "tenant_id": "tenant_integration_001",
        "organization_id": "org_integration_001",
        "workspace_id": "workspace_integration_001",
        "actor_id": "actor.integration",
        "correlation_id": "corr_runtime_integration_001",
        "scope_refs": ["scope.diagnostic"],
        "created_at": "2026-09-23T10:00:00Z",
        "items": [
            {
                "key": "integration-evidence",
                "value": evidence["excerpt"],
                "source_id": evidence["source_id"],
                "evidence_id": evidence["evidence_id"],
                "source_version": evidence["source_version"],
                "content_hash": evidence["content_hash"],
                "anchor": evidence["anchor"],
                "data_classification": "INTERNAL",
                "instruction_authority": False,
            }
        ],
        "evidence_refs": [evidence],
    }
    response = await client.post(
        "/internal/v1/research/run",
        headers=headers(),
        json={
            "research_id": "research.integration.001",
            "run_id": "run.integration.research.001",
            "correlation_id": "corr_runtime_integration_001",
            "domain": "TECHNOLOGY",
            "question": "Analyze authorized evidence.",
            "execution_context": {
                "tenant_id": "tenant_integration_001",
                "organization_id": "org_integration_001",
                "workspace_id": "workspace_integration_001",
                "actor_id": "actor.integration",
                "authority_context": {
                    "role": "RESEARCHER",
                    "authority_level": "REQUESTER",
                },
                "permission_refs": ["research.request"],
                "allowed_tool_ids": [],
                "scope_refs": ["scope.diagnostic"],
                "data_classification": "INTERNAL",
                "correlation_id": "corr_runtime_integration_001",
                "execution_budget": {"max_tokens": 200, "max_steps": 2},
            },
            "scope": ["scope.diagnostic"],
            "context_bundle": context,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["output_state"] == "NEEDS_REVIEW"
    assert result["findings"][0]["evidence_refs"] == [evidence]
    assert result["recommendations"][0]["backlog_candidate"] is True
