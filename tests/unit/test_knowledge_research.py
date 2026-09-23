import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from genesis.contracts import CanonicalContractCatalog
from genesis.memory.ranking import EvidenceAwareRanker
from genesis.memory.retrieval import BackendContextProvider
from genesis.model_gateway import ModelResponse
from genesis.model_gateway.types import ModelRequest
from genesis.research.engine import (
    ComparableDocument,
    ComparisonFindingKind,
    DocumentComparisonIntelligence,
    ResearchEngine,
    ResearchOutputInvalid,
)
from genesis.runtime.execution import BackendToolClient, ToolBoundaryContracts

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def context_bundle() -> dict[str, Any]:
    evidence = {
        "tenant_id": "tenant_research_001",
        "organization_id": "org_research_001",
        "workspace_id": "workspace_research_001",
        "evidence_id": "evidence_policy_001",
        "source_id": "source_policy_001",
        "uri": "urn:alos:source:policy:1",
        "captured_at": "2026-09-18T00:00:00Z",
        "content_hash": "sha256:" + "a" * 64,
        "source_version": "1.0.0",
        "anchor": "lines 1-1",
        "excerpt": "Retention is seven years.",
        "data_classification": "INTERNAL",
        "validation_status": "VALID",
    }
    return {
        "context_id": "context_research_001",
        "tenant_id": "tenant_research_001",
        "organization_id": "org_research_001",
        "workspace_id": "workspace_research_001",
        "actor_id": "actor_research_001",
        "correlation_id": "corr_research_001",
        "scope_refs": ["scope.sources.read"],
        "created_at": "2026-09-18T00:00:00Z",
        "items": [
            {
                "key": "policy-retention",
                "value": "Retention is seven years.",
                "source_id": "source_policy_001",
                "evidence_id": "evidence_policy_001",
                "source_version": "1.0.0",
                "content_hash": "sha256:" + "a" * 64,
                "anchor": "lines 1-1",
                "data_classification": "INTERNAL",
            }
        ],
        "evidence_refs": [evidence],
    }


def research_request() -> dict[str, Any]:
    return {
        "research_id": "research_policy_001",
        "run_id": "run_research_001",
        "correlation_id": "corr_research_001",
        "domain": "MANAGEMENT",
        "question": "What is the retention period?",
        "execution_context": {
            "tenant_id": "tenant_research_001",
            "organization_id": "org_research_001",
            "workspace_id": "workspace_research_001",
            "actor_id": "actor_research_001",
            "authority_context": {"role": "RESEARCHER", "authority_level": "REQUESTER"},
            "permission_refs": ["sources.read"],
            "scope_refs": ["scope.sources.read"],
            "data_classification": "INTERNAL",
            "correlation_id": "corr_research_001",
            "execution_budget": {"max_tokens": 1000, "max_steps": 2},
        },
        "scope": ["retention-policy"],
        "context_bundle": context_bundle(),
    }


class StaticGateway:
    def __init__(self, evidence_id: str = "evidence_policy_001") -> None:
        self.evidence_id = evidence_id
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        content = {
            "findings": [
                {
                    "finding_id": "finding_policy_001",
                    "finding_type": "RESEARCH",
                    "domain": "MANAGEMENT",
                    "title": "Retention period",
                    "statement": "The retention period is seven years.",
                    "severity": "LOW",
                    "confidence": 0.95,
                    "evidence_ids": [self.evidence_id],
                    "limitations": [],
                }
            ],
            "recommendations": [
                {
                    "recommendation_id": "recommendation_policy_001",
                    "summary": "Keep the policy reference current.",
                    "recommended_action": "Create a human-reviewed backlog candidate.",
                    "confidence": 0.8,
                    "finding_ids": ["finding_policy_001"],
                    "evidence_ids": [self.evidence_id],
                    "limitations": [],
                    "backlog_candidate": True,
                }
            ],
            "limitations": ["No external sources were used."],
        }
        return ModelResponse(
            content=json.dumps(content),
            route_id="deterministic-test",
            input_tokens=10,
            output_tokens=20,
        )


@pytest.mark.asyncio
async def test_backend_context_provider_uses_tool_request_and_preserves_correlation() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "tool_call_id": observed["tool_call_id"],
                "run_id": observed["run_id"],
                "tool_id": observed["tool_id"],
                "correlation_id": "corr_research_001",
                "status": "SUCCESS",
                "output": context_bundle(),
                "completed_at": "2026-09-18T00:00:01Z",
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend.test",
    )
    tool_client = BackendToolClient(
        base_url="http://backend.test",
        internal_token=SecretStr("test-only"),
        contracts=ToolBoundaryContracts(CONTRACTS_ROOT),
        client=client,
    )
    provider = BackendContextProvider(
        tool_client=tool_client,
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
    )

    result = await provider.retrieve(
        run_id="run_research_001",
        query="retention",
        execution_context=research_request()["execution_context"],
    )

    assert observed["tool_id"] == "source.search_context"
    assert observed["execution_context"]["correlation_id"] == "corr_research_001"
    assert result["correlation_id"] == "corr_research_001"
    await client.aclose()


@pytest.mark.asyncio
async def test_research_engine_produces_contract_valid_non_authoritative_result() -> None:
    gateway = StaticGateway()
    engine = ResearchEngine(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        model_gateway=gateway,
    )

    result = await engine.research(research_request())

    assert result["output_state"] == "NEEDS_REVIEW"
    assert result["findings"][0]["output_state"] == "AI_INFERRED"
    assert result["recommendations"][0]["author_type"] == "AI"
    assert result["recommendations"][0]["backlog_candidate"] is True
    assert gateway.requests[0].requested_max_tokens == 1000


@pytest.mark.asyncio
async def test_research_engine_rejects_unbound_evidence() -> None:
    engine = ResearchEngine(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        model_gateway=StaticGateway("evidence_unknown_001"),
    )
    with pytest.raises(ResearchOutputInvalid, match="unknown evidence"):
        await engine.research(research_request())


def test_memory_ranker_preserves_only_selected_evidence_lineage() -> None:
    bundle = context_bundle()
    second = {
        **bundle["items"][0],
        "key": "policy-owner",
        "value": "Owner is Finance.",
        "evidence_id": "evidence_owner_001",
    }
    second_ref = {
        **bundle["evidence_refs"][0],
        "evidence_id": "evidence_owner_001",
    }
    bundle["items"].append(second)
    bundle["evidence_refs"].append(second_ref)

    ranked = EvidenceAwareRanker().rank(bundle, query="finance", max_items=1)

    assert ranked["items"][0]["evidence_id"] == "evidence_owner_001"
    assert [item["evidence_id"] for item in ranked["evidence_refs"]] == ["evidence_owner_001"]


def test_document_comparison_adapts_mvp1_negative_findings() -> None:
    content_a = "Owner: Finance\nPolicy year: 2024"
    content_b = "Owner: Legal\nPolicy year: 2026"
    duplicate = ComparableDocument(
        source_id="source_duplicate_001",
        source_version="1.0.0",
        content_hash="sha256:" + hashlib.sha256(content_a.encode()).hexdigest(),
        content=content_a,
    )
    findings = DocumentComparisonIntelligence().compare(
        (
            ComparableDocument(
                source_id="source_policy_001",
                source_version="1.0.0",
                content_hash="sha256:" + hashlib.sha256(content_a.encode()).hexdigest(),
                content=content_a,
            ),
            duplicate,
            ComparableDocument(
                source_id="source_policy_002",
                source_version="1.0.0",
                content_hash="sha256:" + hashlib.sha256(content_b.encode()).hexdigest(),
                content=content_b,
            ),
        ),
        required_fields=("Owner", "Approval"),
        current_year=2026,
    )
    kinds = {finding.kind for finding in findings}
    assert ComparisonFindingKind.DUPLICATE in kinds
    assert ComparisonFindingKind.CONFLICT in kinds
    assert ComparisonFindingKind.MISSING_FIELD in kinds
    assert ComparisonFindingKind.OUTDATED_REFERENCE in kinds
    assert all(finding.requires_human_decision for finding in findings)
