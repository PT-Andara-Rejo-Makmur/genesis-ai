from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from genesis.contracts import CanonicalContractCatalog
from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.research.decision import ResearchRisk
from genesis.research.engine import ResearchEngine
from genesis.research.models import ResearchDomain
from genesis.research.orchestration import (
    ClaimAssessment,
    ClaimComparisonIntelligence,
    ClaimKind,
    DelegatedResearchInput,
    EvidenceQualityPolicy,
    EvidenceUsability,
    FindingRecommendationBuilder,
    ResearchClaimExtractor,
    ResearchEvidenceItem,
    ResearchOrchestrationFailure,
    ResearchOrchestrator,
    ResearchQuestionPlanner,
    ResearchRetrievalRequest,
    ResearchRetrievalResult,
    RetrievalStatus,
    SourceMode,
)
from genesis.research.tool_selection import (
    AuthorizedResearchTool,
    ResearchToolCategory,
)

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


class SequenceGateway:
    def __init__(self, responses: Sequence[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self.responses.pop(0)


class FakeProvider:
    def __init__(self, results: Sequence[ResearchRetrievalResult | Exception]) -> None:
        self.results = list(results)
        self.requests: list[ResearchRetrievalRequest] = []

    async def retrieve(self, request: ResearchRetrievalRequest) -> ResearchRetrievalResult:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def response(payload: Any, *, tokens: int = 10, cost: float = 0.1) -> ModelResponse:
    return ModelResponse(
        content=json.dumps(payload),
        route_id="route.h7.test",
        input_tokens=tokens // 2,
        output_tokens=tokens - tokens // 2,
        cost=cost,
    )


def subquery(
    domain: ResearchDomain,
    subquery_id: str = "subquery_current_001",
    *,
    need: str = "CURRENT_STATE",
) -> dict[str, Any]:
    return {
        "subquery_id": subquery_id,
        "question": f"What evidence is required for {domain.value}?",
        "domain": domain.value,
        "evidence_need": need,
        "preferred_source_categories": [
            "INTERNAL_DOCUMENT",
            "PUBLIC_DATASET",
            "EXTERNAL_RESEARCH",
        ],
        "required_scope_refs": ["scope.research"],
        "materiality": "HIGH",
        "reason_code": f"DOMAIN_{domain.value}",
    }


def plan_payload(
    domain: ResearchDomain,
    *subqueries: dict[str, Any],
) -> dict[str, Any]:
    return {
        "subqueries": list(subqueries or (subquery(domain),)),
        "limitations": [],
    }


def claim_payload(*claims: dict[str, Any]) -> dict[str, Any]:
    return {"claims": list(claims)}


def fact(
    evidence_id: str,
    *,
    claim_id: str = "claim_fact_001",
    topic: str = "research-topic",
    statement: str = "The governed evidence supports the proposal.",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "normalized_topic": topic,
        "statement": statement,
        "kind": "FACT",
        "evidence_ids": [evidence_id],
    }


def assumption(claim_id: str = "claim_assumption_001") -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "normalized_topic": "adoption",
        "statement": "Stakeholders are assumed to have implementation capacity.",
        "kind": "ASSUMPTION",
        "evidence_ids": [],
    }


def research_request(
    domain: ResearchDomain = ResearchDomain.TECHNOLOGY,
    *,
    context_bundle: dict[str, Any] | None = None,
    classification: str = "INTERNAL",
    allowed_tools: Sequence[str] = (),
    permission_refs: Sequence[str] = ("research.external.read",),
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "research_id": "research_h7_001",
        "run_id": "run_h7_001",
        "correlation_id": "corr_h7_001",
        "domain": domain.value,
        "question": "What should PT ARM evaluate?",
        "execution_context": {
            "tenant_id": "tenant_h7_001",
            "organization_id": "organization_h7_001",
            "workspace_id": "workspace_h7_001",
            "actor_id": "actor_h7_001",
            "authority_context": {
                "role": "researcher",
                "authority_level": "REQUESTER",
            },
            "permission_refs": list(permission_refs),
            "allowed_tool_ids": list(allowed_tools),
            "scope_refs": ["scope.research"],
            "data_classification": classification,
            "correlation_id": "corr_h7_001",
            "execution_budget": {
                "max_tokens": 4_000,
                "max_cost": 4,
                "max_steps": 3,
            },
        },
        "scope": ["research"],
    }
    if context_bundle is not None:
        result["context_bundle"] = context_bundle
    return result


def evidence_ref(
    evidence_id: str = "evidence_internal_001",
    *,
    source_id: str = "source_internal_001",
    source_version: str = "1.0.0",
    source_type: str = "INTERNAL",
    freshness: str = "CURRENT",
    reliability: str = "HIGH",
    content_trust: str | None = None,
    **changes: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tenant_id": "tenant_h7_001",
        "organization_id": "organization_h7_001",
        "workspace_id": "workspace_h7_001",
        "run_id": "run_h7_001",
        "correlation_id": "corr_h7_001",
        "scope_refs": ["scope.research"],
        "evidence_id": evidence_id,
        "source_id": source_id,
        "uri": f"urn:alos:evidence:{evidence_id}",
        "captured_at": "2026-09-22T10:00:00Z",
        "retrieved_at": "2026-09-22T10:00:00Z",
        "content_hash": "sha256:" + ("b" * 64),
        "source_version": source_version,
        "anchor": "section:1",
        "excerpt": "Bounded governed evidence.",
        "data_classification": "INTERNAL",
        "source_type": source_type,
        "freshness": freshness,
        "reliability": reliability,
        "content_trust": content_trust
        or ("UNTRUSTED" if source_type == "EXTERNAL" else "GOVERNED"),
        "instruction_authority": False,
        "validation_status": "VALID",
    }
    result.update(changes)
    return result


def evidence_item(
    evidence_id: str = "evidence_internal_001",
    *,
    category: ResearchToolCategory = ResearchToolCategory.INTERNAL_DOCUMENT,
    subquery_ids: tuple[str, ...] = (),
    child_task_id: str | None = None,
    **ref_changes: Any,
) -> ResearchEvidenceItem:
    return ResearchEvidenceItem(
        evidence_ref=evidence_ref(evidence_id, **ref_changes),
        content=f"Evidence content for {evidence_id}.",
        category=category,
        subquery_ids=subquery_ids,
        child_task_id=child_task_id,
    )


def context_bundle(item: ResearchEvidenceItem) -> dict[str, Any]:
    ref = item.evidence_ref
    return {
        "context_id": "context_h7_001",
        "tenant_id": "tenant_h7_001",
        "organization_id": "organization_h7_001",
        "workspace_id": "workspace_h7_001",
        "actor_id": "actor_h7_001",
        "correlation_id": "corr_h7_001",
        "scope_refs": ["scope.research"],
        "created_at": "2026-09-22T10:00:00Z",
        "items": [
            {
                "key": "h7-evidence",
                "value": item.content,
                "source_id": ref["source_id"],
                "evidence_id": ref["evidence_id"],
                "source_version": ref["source_version"],
                "content_hash": ref["content_hash"],
                "anchor": ref["anchor"],
                "data_classification": ref["data_classification"],
            }
        ],
        "evidence_refs": [ref],
    }


def external_tool(**changes: Any) -> AuthorizedResearchTool:
    values: dict[str, Any] = {
        "tool_id": "research.external.retrieve",
        "category": ResearchToolCategory.EXTERNAL_RESEARCH,
        "domains": tuple(ResearchDomain),
        "permission_refs": ("research.external.read",),
        "scope_refs": ("scope.research",),
        "estimated_cost": 1,
    }
    values.update(changes)
    return AuthorizedResearchTool.model_validate(values)


def make_orchestrator(
    gateway: SequenceGateway,
    provider: FakeProvider | None = None,
    *,
    max_subqueries: int = 8,
) -> ResearchOrchestrator:
    contracts = CanonicalContractCatalog(CONTRACTS_ROOT)
    return ResearchOrchestrator(
        contracts=contracts,
        question_planner=ResearchQuestionPlanner(
            model_gateway=gateway, max_subqueries=max_subqueries
        ),
        claim_extractor=ResearchClaimExtractor(model_gateway=gateway),
        evidence_provider=provider,
    )


@pytest.mark.asyncio
async def test_internal_only_research_uses_no_provider_and_binds_evidence() -> None:
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_internal_001"), assumption())),
        )
    )
    provider = FakeProvider(())
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(), existing_evidence=(evidence_item(),)
    )
    assert result.source_mode is SourceMode.INTERNAL_ONLY
    assert provider.requests == []
    assert result.findings[0].evidence_ids == ("evidence_internal_001",)
    assert result.assumptions[0].kind is ClaimKind.ASSUMPTION
    assert result.recommendations[0].requires_human_review is True
    assert result.canonical_result["output_state"] == "NEEDS_REVIEW"
    assert result.canonical_result["findings"][0]["finding_type"] == "RESEARCH"


@pytest.mark.asyncio
async def test_external_only_uses_governed_provider_and_keeps_untrusted_semantics() -> None:
    external = evidence_item(
        "evidence_external_001",
        category=ResearchToolCategory.EXTERNAL_RESEARCH,
        source_id="source_external_001",
        source_type="EXTERNAL",
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(external,)),)
    )
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_external_001"))),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    assert result.source_mode is SourceMode.EXTERNAL_ONLY
    assert len(provider.requests) == 1
    assert result.evidence_items[0].evidence_ref["content_trust"] == "UNTRUSTED"
    assert result.evidence_items[0].instruction_authority is False


@pytest.mark.asyncio
async def test_mixed_sources_preserve_independent_corroboration() -> None:
    internal = evidence_item(
        subquery_ids=("subquery_internal_001",),
    )
    external = evidence_item(
        "evidence_external_001",
        category=ResearchToolCategory.EXTERNAL_RESEARCH,
        subquery_ids=("subquery_external_001",),
        source_id="source_external_001",
        source_type="EXTERNAL",
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(external,)),)
    )
    gateway = SequenceGateway(
        (
            response(
                plan_payload(
                    ResearchDomain.TECHNOLOGY,
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_internal_001"),
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_external_001"),
                )
            ),
            response(
                claim_payload(
                    fact("evidence_internal_001", claim_id="claim_internal_001"),
                    fact("evidence_external_001", claim_id="claim_external_001"),
                )
            ),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        existing_evidence=(internal,),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    assert result.source_mode is SourceMode.MIXED
    assert {item.evidence_id for item in result.evidence_items} == {
        "evidence_internal_001",
        "evidence_external_001",
    }
    assert len(result.corroborations) == 1
    assert result.duplicates == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    (
        RetrievalStatus.FAILED,
        RetrievalStatus.TIMEOUT,
        RetrievalStatus.DENIED,
        RetrievalStatus.NO_RESULT,
    ),
)
async def test_retrieval_failure_is_one_attempt_and_never_fabricates(
    status: RetrievalStatus,
) -> None:
    provider = FakeProvider(
        (
            ResearchRetrievalResult(
                status=status,
                limitations=(f"provider returned {status.value}",),
                error_code=f"PROVIDER_{status.value}",
            ),
        )
    )
    gateway = SequenceGateway((response(plan_payload(ResearchDomain.TECHNOLOGY)),))
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    assert len(provider.requests) == 1
    assert len(gateway.requests) == 1
    assert result.findings == () and result.recommendations == ()
    assert result.gaps
    assert f"RETRIEVAL_{status.value}" in " ".join(result.limitations)


@pytest.mark.asyncio
async def test_unauthorized_restricted_or_cost_blocked_external_is_not_called() -> None:
    cases = (
        research_request(),
        research_request(
            classification="RESTRICTED",
            allowed_tools=("research.external.retrieve",),
        ),
        research_request(allowed_tools=("research.external.retrieve",)),
    )
    tools = (external_tool(), external_tool(), external_tool(estimated_cost=3))
    costs = (2, 2, 1)
    for request, tool, maximum_cost in zip(cases, tools, costs, strict=True):
        provider = FakeProvider(())
        gateway = SequenceGateway((response(plan_payload(ResearchDomain.TECHNOLOGY)),))
        result = await make_orchestrator(gateway, provider).orchestrate(
            request,
            authorized_tools=(tool,),
            maximum_external_cost=maximum_cost,
        )
        assert provider.requests == []
        assert result.findings == ()
        assert "NO_AUTHORIZED_COST_SAFE_TOOL" in " ".join(result.limitations)


def test_quality_is_monotonic_and_stale_unknown_are_not_current_fact_strength() -> None:
    policy = EvidenceQualityPolicy()
    context = research_request()["execution_context"]
    high = policy.assess(evidence_item(), context)
    medium = policy.assess(evidence_item(reliability="MEDIUM"), context)
    low = policy.assess(evidence_item(reliability="LOW"), context)
    stale = policy.assess(evidence_item(freshness="STALE"), context)
    unknown = policy.assess(evidence_item(freshness="UNKNOWN"), context)
    assert high.confidence_cap > medium.confidence_cap > low.confidence_cap
    assert stale.usability is EvidenceUsability.HISTORICAL_ONLY
    assert stale.confidence_cap < medium.confidence_cap
    assert unknown.confidence_cap < medium.confidence_cap


def test_missing_identity_scope_or_provenance_is_excluded() -> None:
    policy = EvidenceQualityPolicy()
    context = research_request()["execution_context"]
    invalid = evidence_item(workspace_id="workspace_other", source_version="")
    assessment = policy.assess(invalid, context)
    assert assessment.usability is EvidenceUsability.EXCLUDED
    assert assessment.confidence_cap == 0


def test_external_governed_content_is_rejected_structurally() -> None:
    with pytest.raises(ValidationError):
        evidence_item(source_type="EXTERNAL", content_trust="GOVERNED")


def assessed_claim(
    claim_id: str,
    statement: str,
    evidence_id: str,
    source_id: str,
    version: str,
) -> ClaimAssessment:
    return ClaimAssessment(
        claim_id=claim_id,
        normalized_topic="policy-owner",
        statement=statement,
        kind=ClaimKind.FACT,
        evidence_ids=(evidence_id,),
        source_ids=(source_id,),
        source_versions=(version,),
        confidence=0.95,
    )


def test_compare_distinguishes_duplicate_corroboration_version_and_conflict() -> None:
    quality = EvidenceQualityPolicy()
    context = research_request()["execution_context"]
    items = (
        evidence_item("evidence_a", source_id="source_a", source_version="1"),
        evidence_item("evidence_b", source_id="source_a", source_version="1"),
        evidence_item("evidence_c", source_id="source_c", source_version="1"),
        evidence_item("evidence_d", source_id="source_a", source_version="2"),
    )
    assessments = tuple(quality.assess(item, context) for item in items)
    claims = (
        assessed_claim("claim_a", "Finance owns policy.", "evidence_a", "source_a", "1"),
        assessed_claim("claim_b", "Finance owns policy.", "evidence_b", "source_a", "1"),
        assessed_claim("claim_c", "Finance owns policy.", "evidence_c", "source_c", "1"),
        assessed_claim("claim_d", "Legal owns policy.", "evidence_d", "source_a", "2"),
    )
    duplicates, corroborations, conflicts = ClaimComparisonIntelligence().compare(
        claims, assessments
    )
    assert duplicates and corroborations
    assert conflicts[0].unresolved is True
    assert set(conflicts[0].source_versions) == {"1", "2"}


@pytest.mark.asyncio
async def test_conflict_and_stale_quality_cap_findings_and_recommendations() -> None:
    current = evidence_item("evidence_current", source_id="source_policy", source_version="2")
    stale = evidence_item(
        "evidence_stale",
        source_id="source_policy",
        source_version="1",
        freshness="STALE",
    )
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.MANAGEMENT)),
            response(
                claim_payload(
                    fact(
                        "evidence_current",
                        claim_id="claim_current",
                        topic="policy-owner",
                        statement="Finance owns the policy.",
                    ),
                    fact(
                        "evidence_stale",
                        claim_id="claim_stale",
                        topic="policy-owner",
                        statement="Legal owns the policy.",
                    ),
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(ResearchDomain.MANAGEMENT),
        existing_evidence=(current, stale),
    )
    assert result.conflicts[0].unresolved is True
    assert all(item.confidence <= 0.5 for item in result.findings)
    assert all("UNRESOLVED_CONFLICT" in item.limitations for item in result.recommendations)


@pytest.mark.asyncio
async def test_unknown_evidence_citation_fails_closed() -> None:
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_unknown"))),
        )
    )
    with pytest.raises(ResearchOrchestrationFailure) as raised:
        await make_orchestrator(gateway).orchestrate(
            research_request(), existing_evidence=(evidence_item(),)
        )
    assert raised.value.code == "RESEARCH_EVIDENCE_UNKNOWN"


@pytest.mark.asyncio
async def test_invalid_plan_json_and_scope_expansion_fail_closed() -> None:
    invalid = SequenceGateway((response({"wrong": []}),))
    with pytest.raises(ResearchOrchestrationFailure) as malformed:
        await make_orchestrator(invalid).orchestrate(research_request())
    assert malformed.value.code == "RESEARCH_PLAN_INVALID"

    expanded = plan_payload(ResearchDomain.TECHNOLOGY)
    expanded["subqueries"][0]["required_scope_refs"] = ["scope.admin"]
    gateway = SequenceGateway((response(expanded),))
    with pytest.raises(ResearchOrchestrationFailure) as denied:
        await make_orchestrator(gateway).orchestrate(research_request())
    assert denied.value.code == "RESEARCH_PLAN_AUTHORITY_EXPANSION"


@pytest.mark.asyncio
async def test_memory_and_h6_child_inputs_preserve_scope_and_completion_policy() -> None:
    memory = evidence_item(
        "evidence_memory_001",
        category=ResearchToolCategory.MEMORY,
        reliability="MEDIUM",
    )
    child = evidence_item("evidence_child_001", child_task_id="child_task_h7_001")
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(
                claim_payload(
                    fact("evidence_memory_001", claim_id="claim_memory"),
                    fact("evidence_child_001", claim_id="claim_child"),
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(),
        memory_evidence=(memory,),
        delegated_inputs=(
            DelegatedResearchInput(
                child_task_id="child_task_h7_001",
                status="COMPLETED",
                validation_status="VALID",
                evidence_items=(child,),
            ),
            DelegatedResearchInput(
                child_task_id="child_task_h7_failed",
                status="FAILED",
                validation_status="VALID",
                evidence_items=(evidence_item("evidence_failed_child"),),
            ),
        ),
        risk=ResearchRisk.LOW,
    )
    assert {item.evidence_id for item in result.evidence_items} == {
        "evidence_memory_001",
        "evidence_child_001",
    }
    assert "CHILD_child_task_h7_failed_FAILED_NOT_PROMOTED" in result.limitations


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", list(ResearchDomain))
async def test_four_domains_use_one_orchestrator_and_canonical_projection(
    domain: ResearchDomain,
) -> None:
    item = evidence_item(f"evidence_{domain.value.lower()}")
    gateway = SequenceGateway(
        (
            response(plan_payload(domain, subquery(domain, need="RISK"))),
            response(claim_payload(fact(item.evidence_id))),
        )
    )
    orchestrator = make_orchestrator(gateway)
    result = await orchestrator.orchestrate(
        research_request(domain), existing_evidence=(item,)
    )
    assert type(orchestrator) is ResearchOrchestrator
    assert result.plan.domain is domain
    assert result.plan.subqueries[0].evidence_need.value == "RISK"
    assert result.findings[0].domain is domain
    assert result.canonical_result["findings"][0]["domain"] == domain.value
    assert result.recommendations[0].requires_human_review is True


@pytest.mark.asyncio
async def test_research_engine_keeps_one_contract_valid_public_result_path() -> None:
    item = evidence_item()
    request = research_request(context_bundle=context_bundle(item))
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_internal_001"))),
        )
    )
    orchestrator = make_orchestrator(gateway)
    engine = ResearchEngine(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT),
        model_gateway=gateway,
        orchestrator=orchestrator,
    )
    result = await engine.research(request)
    assert set(result) <= {
        "research_id",
        "run_id",
        "tenant_id",
        "organization_id",
        "workspace_id",
        "correlation_id",
        "output_state",
        "findings",
        "recommendations",
        "evidence_bundle",
        "limitations",
        "completed_at",
    }
    assert result["findings"][0]["output_state"] == "AI_INFERRED"
    assert result["recommendations"][0]["author_type"] == "AI"
    assert result["recommendations"][0]["backlog_candidate"] is True


def test_builder_never_creates_finding_from_assumption_or_gap_only() -> None:
    claims = (
        ClaimAssessment(
            claim_id="claim_assumption",
            normalized_topic="capacity",
            statement="Capacity is assumed.",
            kind=ClaimKind.ASSUMPTION,
            evidence_ids=(),
            source_ids=(),
            source_versions=(),
            confidence=0.5,
        ),
        ClaimAssessment(
            claim_id="claim_gap",
            normalized_topic="cost",
            statement="Cost evidence is missing.",
            kind=ClaimKind.GAP,
            evidence_ids=(),
            source_ids=(),
            source_versions=(),
            confidence=0.1,
        ),
    )
    findings, recommendations = FindingRecommendationBuilder().build(
        domain=ResearchDomain.TECHNOLOGY,
        claims=claims,
        conflicts=(),
        corroborations=(),
        assessments=(),
    )
    assert findings == () and recommendations == ()
