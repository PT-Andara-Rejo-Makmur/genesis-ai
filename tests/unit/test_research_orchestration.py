from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.model_gateway.types import ModelRequest, ModelResponse
from genesis.research.decision import ResearchRisk
from genesis.research.engine import ResearchEngine
from genesis.research.models import ResearchDomain
from genesis.research.orchestration import (
    ClaimAssessment,
    ClaimComparisonIntelligence,
    ClaimKind,
    ConflictAssessment,
    ConflictType,
    DelegatedResearchInput,
    EvidenceQualityPolicy,
    EvidenceRelevance,
    EvidenceRelevancePolicy,
    EvidenceUsability,
    FindingRecommendationBuilder,
    ResearchClaimExtractor,
    ResearchEvidenceAdmissionPolicy,
    ResearchEvidenceItem,
    ResearchOrchestrationFailure,
    ResearchOrchestrator,
    ResearchQuestionPlanner,
    ResearchRecommendationSynthesizer,
    ResearchRetrievalRequest,
    ResearchRetrievalResult,
    ResearchSubquery,
    RetrievalStatus,
    SourceMode,
    evidence_items_from_context,
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
        if not self.responses and request.purpose == "evidence-bound-recommendation-synthesis":
            payload = json.loads(str(request.messages[-1]["content"]))
            finding = payload["findings"][0]
            facts = {
                item["claim_id"]: item for item in payload["fact_claims"]
            }
            fact_ids = finding["fact_claim_ids"]
            topics = {facts[item]["normalized_topic"] for item in fact_ids}
            assumptions = [
                item["claim_id"]
                for item in payload["assumptions"]
                if item["normalized_topic"] in topics
            ]
            domain_action = payload["domain_profile"]["allowed_recommendations"][0]
            return response(
                {
                    "recommendations": [
                        {
                            "recommendation_id": "recommendation_h7_test_001",
                            "finding_ids": [finding["finding_id"]],
                            "fact_claim_ids": fact_ids,
                            "conflict_ids": finding["conflict_ids"],
                            "assumption_ids": assumptions,
                            "proposed_action": (
                                f"Conduct a governed {domain_action.lower()} using the cited "
                                "finding and submit measured outcomes for human review."
                            ),
                            "evidence_ids": finding["evidence_ids"],
                            "limitations": [],
                            "requires_human_review": True,
                            "backlog_candidate": True,
                        }
                    ]
                }
            )
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
        "question": f"What current {domain.value} evidence supports the proposal?",
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


def recommendation_payload(
    *,
    finding_id: str = "finding_placeholder",
    fact_claim_ids: Sequence[str] = ("claim_fact_001",),
    evidence_ids: Sequence[str] = ("evidence_internal_001",),
    conflict_ids: Sequence[str] = (),
    assumption_ids: Sequence[str] = (),
    action: str = "Run a governed benchmark and submit measured results for human review.",
) -> dict[str, Any]:
    return {
        "recommendations": [
            {
                "recommendation_id": "recommendation_h7_delta_001",
                "finding_ids": [finding_id],
                "fact_claim_ids": list(fact_claim_ids),
                "conflict_ids": list(conflict_ids),
                "assumption_ids": list(assumption_ids),
                "proposed_action": action,
                "evidence_ids": list(evidence_ids),
                "limitations": [],
                "requires_human_review": True,
                "backlog_candidate": True,
            }
        ]
    }


def finding_id(claim_id: str) -> str:
    return "finding_" + hashlib.sha256(claim_id.encode()).hexdigest()[:20]


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
    subquery_ids: tuple[str, ...] = ("subquery_current_001",),
    child_task_id: str | None = None,
    content: str | None = None,
    **ref_changes: Any,
) -> ResearchEvidenceItem:
    return ResearchEvidenceItem(
        evidence_ref=evidence_ref(evidence_id, **ref_changes),
        content=content or f"Current technology proposal evidence for {evidence_id}.",
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
        recommendation_synthesizer=ResearchRecommendationSynthesizer(
            model_gateway=gateway
        ),
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


def test_external_governed_content_is_rejected_by_central_admission() -> None:
    item = evidence_item(source_type="EXTERNAL", content_trust="GOVERNED")
    admitted, assessment = ResearchEvidenceAdmissionPolicy(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT)
    ).admit(item, research_request()["execution_context"])
    assert admitted is None
    assert assessment.admitted is False


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


def test_relevance_is_deterministic_and_subquery_specific() -> None:
    policy = EvidenceRelevancePolicy()
    related = evidence_item(
        subquery_ids=(),
        content="Current warehouse demand and regional occupancy evidence.",
    )
    unrelated = evidence_item(
        "evidence_leave_sop",
        subquery_ids=(),
        content="Employee annual leave SOP and holiday approval procedure.",
    )
    demand = ResearchSubquery.model_validate(
        subquery(
            ResearchDomain.PROPERTY_MARKET,
            "subquery_demand",
            need="CURRENT_STATE",
        )
        | {"question": "What is current warehouse demand in the region?"}
    )
    governance = ResearchSubquery.model_validate(
        subquery(
            ResearchDomain.MANAGEMENT,
            "subquery_governance",
            need="GOVERNANCE",
        )
        | {"question": "Which employee leave SOP governs holiday approval?"}
    )
    first = policy.assess(related, demand)
    assert first == policy.assess(related, demand)
    assert first.relevance is EvidenceRelevance.RELEVANT
    assert policy.assess(unrelated, demand).relevance is EvidenceRelevance.IRRELEVANT
    assert policy.assess(unrelated, governance).relevance is EvidenceRelevance.RELEVANT


def test_explicit_relevance_binding_has_precedence() -> None:
    policy = EvidenceRelevancePolicy()
    target = ResearchSubquery.model_validate(
        subquery(ResearchDomain.TECHNOLOGY, "subquery_target")
    )
    ambiguous = evidence_item(
        subquery_ids=("subquery_target",),
        content="No lexical relationship is required for explicit binding.",
    )
    mismatch = evidence_item(
        "evidence_mismatch",
        subquery_ids=("subquery_other",),
        content="Current technology proposal evidence supports the proposal.",
    )
    assert policy.assess(ambiguous, target).relevance is EvidenceRelevance.EXACT
    assert policy.assess(mismatch, target).relevance is EvidenceRelevance.IRRELEVANT


def test_context_projection_remains_untagged_and_relevance_aware() -> None:
    original = evidence_item(
        subquery_ids=(),
        content="Current warehouse demand and regional occupancy evidence.",
    )
    projected = evidence_items_from_context(context_bundle(original))[0]
    assert projected.subquery_ids == ()
    demand = ResearchSubquery.model_validate(
        subquery(ResearchDomain.PROPERTY_MARKET, "subquery_demand")
        | {"question": "What is current warehouse demand in the region?"}
    )
    sop = ResearchSubquery.model_validate(
        subquery(ResearchDomain.MANAGEMENT, "subquery_sop", need="GOVERNANCE")
        | {"question": "Which employee leave SOP governs holiday approval?"}
    )
    policy = EvidenceRelevancePolicy()
    assert policy.assess(projected, demand).relevance is EvidenceRelevance.RELEVANT
    assert policy.assess(projected, sop).relevance is EvidenceRelevance.IRRELEVANT


@pytest.mark.parametrize(
    ("changes", "reason"),
    (
        ({"source_type": "ALIEN"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"freshness": "FUTURE"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"reliability": "PERFECT"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"content_hash": "not-a-hash"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"uri": "not a uri"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"captured_at": "yesterday"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"data_classification": "SECRET"}, "CANONICAL_EVIDENCE_INVALID"),
        ({"instruction_authority": True}, "CANONICAL_EVIDENCE_INVALID"),
        ({"tenant_id": "tenant_other"}, "EVIDENCE_IDENTITY_MISMATCH"),
        ({"organization_id": "organization_other"}, "EVIDENCE_IDENTITY_MISMATCH"),
        ({"workspace_id": "workspace_other"}, "EVIDENCE_IDENTITY_MISMATCH"),
        ({"scope_refs": ["scope.admin"]}, "EVIDENCE_SCOPE_EXPANSION"),
        ({"data_classification": "CONFIDENTIAL"}, "EVIDENCE_CLASSIFICATION_EXPANSION"),
        ({"validation_status": "INVALID"}, "EVIDENCE_NOT_VALID"),
    ),
)
def test_canonical_evidence_admission_rejects_malformed_or_expanded_refs(
    changes: dict[str, Any], reason: str
) -> None:
    policy = ResearchEvidenceAdmissionPolicy(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT)
    )
    admitted, assessment = policy.admit(
        evidence_item(**changes), research_request()["execution_context"]
    )
    assert admitted is None
    assert assessment.reason_codes == (reason,)


def test_valid_canonical_evidence_is_admitted_without_lineage_mutation() -> None:
    item = evidence_item()
    admitted, assessment = ResearchEvidenceAdmissionPolicy(
        contracts=CanonicalContractCatalog(CONTRACTS_ROOT)
    ).admit(item, research_request()["execution_context"])
    assert admitted is not None
    assert admitted.evidence_ref == item.evidence_ref
    assert assessment.admitted is True


@pytest.mark.asyncio
async def test_irrelevant_internal_evidence_does_not_suppress_retrieval() -> None:
    unrelated = evidence_item(
        "evidence_leave_sop",
        subquery_ids=(),
        content="Employee annual leave SOP and holiday approval procedure.",
    )
    external = evidence_item(
        "evidence_market_demand",
        source_type="EXTERNAL",
        source_id="source_market",
        category=ResearchToolCategory.EXTERNAL_RESEARCH,
        content="Current warehouse demand in the region increased.",
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(external,)),)
    )
    plan = plan_payload(ResearchDomain.PROPERTY_MARKET)
    plan["subqueries"][0]["question"] = "What is current warehouse demand in the region?"
    gateway = SequenceGateway(
        (
            response(plan),
            response(claim_payload(fact("evidence_market_demand"))),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(
            ResearchDomain.PROPERTY_MARKET,
            allowed_tools=("research.external.retrieve",),
        ),
        existing_evidence=(unrelated,),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    assert len(provider.requests) == 1
    assert result.findings
    assert "evidence_leave_sop" not in {item.evidence_id for item in result.evidence_items}


@pytest.mark.asyncio
async def test_invalid_provider_sibling_is_rejected_before_claim_model() -> None:
    invalid = evidence_item(
        "evidence_invalid_provider",
        source_type="ALIEN",
    )
    valid = evidence_item(
        "evidence_valid_provider",
        source_type="EXTERNAL",
        source_id="source_external_valid",
        category=ResearchToolCategory.EXTERNAL_RESEARCH,
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(invalid, valid)),)
    )
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_valid_provider"))),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    claim_request = json.loads(str(gateway.requests[1].messages[-1]["content"]))
    serialized = json.dumps(claim_request)
    assert "evidence_invalid_provider" not in serialized
    assert "evidence_valid_provider" in serialized
    assert any(not item.admitted for item in result.evidence_admissions)


@pytest.mark.asyncio
async def test_all_invalid_provider_evidence_yields_no_fabricated_result() -> None:
    invalid = evidence_item("evidence_invalid_provider", source_type="ALIEN")
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(invalid,)),)
    )
    gateway = SequenceGateway((response(plan_payload(ResearchDomain.TECHNOLOGY)),))
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        authorized_tools=(external_tool(),),
        maximum_external_cost=2,
    )
    assert len(gateway.requests) == 1
    assert result.findings == () and result.recommendations == ()
    assert "CANONICAL_EVIDENCE_INVALID" in " ".join(result.limitations)


@pytest.mark.asyncio
async def test_recommendation_failure_preserves_findings_and_rejects_unknown_assumption() -> None:
    relevant_assumption = {
        "claim_id": "claim_assumption_relevant",
        "normalized_topic": "research-topic",
        "statement": "Adoption capacity is assumed.",
        "kind": "ASSUMPTION",
        "evidence_ids": [],
    }
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(
                claim_payload(fact("evidence_internal_001"), relevant_assumption)
            ),
            response(
                recommendation_payload(
                    finding_id=finding_id("claim_fact_001"),
                    assumption_ids=("claim_unknown",),
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(), existing_evidence=(evidence_item(),)
    )
    assert result.findings
    assert result.recommendations == ()
    assert "RECOMMENDATION_ASSUMPTION_UNKNOWN" in result.limitations


@pytest.mark.asyncio
async def test_recommendation_maps_only_relevant_assumption_and_accounts_usage() -> None:
    relevant = {
        "claim_id": "claim_assumption_relevant",
        "normalized_topic": "research-topic",
        "statement": "Adoption capacity is assumed.",
        "kind": "ASSUMPTION",
        "evidence_ids": [],
    }
    unrelated = {
        "claim_id": "claim_assumption_unrelated",
        "normalized_topic": "employee-leave",
        "statement": "Leave capacity is assumed.",
        "kind": "ASSUMPTION",
        "evidence_ids": [],
    }
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY), tokens=10, cost=0.1),
            response(
                claim_payload(fact("evidence_internal_001"), relevant, unrelated),
                tokens=12,
                cost=0.2,
            ),
            response(
                recommendation_payload(
                    finding_id=finding_id("claim_fact_001"),
                    assumption_ids=("claim_assumption_relevant",),
                    action=(
                        "Run a security and compatibility benchmark, then submit the measured "
                        "results for governed human adoption review."
                    ),
                ),
                tokens=14,
                cost=0.3,
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(), existing_evidence=(evidence_item(),)
    )
    assert result.recommendations[0].assumption_ids == (
        "claim_assumption_relevant",
    )
    assert result.usage.total_tokens == 36
    assert result.usage.estimated_cost == pytest.approx(0.6)
    assert len(gateway.requests) == 3


def test_one_claim_preserves_multiple_conflicts_deterministically() -> None:
    item = evidence_item()
    quality = EvidenceQualityPolicy().assess(
        item, research_request()["execution_context"]
    )
    primary = assessed_claim(
        "claim_primary", "Finance owns policy.", item.evidence_id, "source_a", "1"
    )
    other = assessed_claim(
        "claim_other", "Legal owns policy.", item.evidence_id, "source_a", "2"
    )
    conflicts = (
        ConflictAssessment(
            conflict_id="conflict_b",
            topic="policy-owner",
            competing_claim_ids=("claim_primary", "claim_other"),
            evidence_ids=(item.evidence_id,),
            source_ids=("source_a",),
            source_versions=("1", "2"),
            conflict_type=ConflictType.SOURCE_VERSION,
            limitations=("UNRESOLVED_SOURCE_CONFLICT",),
        ),
        ConflictAssessment(
            conflict_id="conflict_a",
            topic="policy-owner",
            competing_claim_ids=("claim_primary", "claim_other"),
            evidence_ids=(item.evidence_id,),
            source_ids=("source_a",),
            source_versions=("1", "2"),
            conflict_type=ConflictType.CLAIM_CONTRADICTION,
            limitations=("UNRESOLVED_SOURCE_CONFLICT",),
        ),
    )
    findings = FindingRecommendationBuilder().build_findings(
        domain=ResearchDomain.MANAGEMENT,
        claims=(primary, other),
        conflicts=conflicts,
        corroborations=(),
        assessments=(quality,),
    )
    assert findings[0].conflict_ids == ("conflict_a", "conflict_b")
    assert findings[0].confidence <= 0.5


@pytest.mark.asyncio
async def test_cumulative_external_retrieval_cost_blocks_second_provider_call() -> None:
    first = evidence_item(
        "evidence_first_external",
        source_type="EXTERNAL",
        source_id="source_first",
        category=ResearchToolCategory.EXTERNAL_RESEARCH,
        subquery_ids=("subquery_first",),
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(first,)),)
    )
    gateway = SequenceGateway(
        (
            response(
                plan_payload(
                    ResearchDomain.TECHNOLOGY,
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_first"),
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_second"),
                )
            ),
            response(claim_payload(fact("evidence_first_external"))),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=("research.external.retrieve",)),
        authorized_tools=(external_tool(estimated_cost=1),),
        maximum_external_cost=1.5,
    )
    assert len(provider.requests) == 1
    assert result.reserved_external_retrieval_cost == 1
    assert "CUMULATIVE_RETRIEVAL_COST_LIMIT" in " ".join(result.limitations)


@pytest.mark.asyncio
async def test_generic_retrieval_cost_is_cumulative_and_external_zero_does_not_block_connector(
) -> None:
    first = evidence_item(
        "evidence_first_connector",
        category=ResearchToolCategory.CONNECTOR,
        subquery_ids=("subquery_first",),
    )
    provider = FakeProvider(
        (ResearchRetrievalResult(status=RetrievalStatus.SUCCESS, items=(first,)),)
    )
    connector = AuthorizedResearchTool(
        tool_id="research.connector.retrieve",
        category=ResearchToolCategory.CONNECTOR,
        domains=tuple(ResearchDomain),
        scope_refs=("scope.research",),
        estimated_cost=1,
    )
    gateway = SequenceGateway(
        (
            response(
                plan_payload(
                    ResearchDomain.TECHNOLOGY,
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_first"),
                    subquery(ResearchDomain.TECHNOLOGY, "subquery_second"),
                )
            ),
            response(claim_payload(fact("evidence_first_connector"))),
        )
    )
    result = await make_orchestrator(gateway, provider).orchestrate(
        research_request(allowed_tools=(connector.tool_id,)),
        authorized_tools=(connector,),
        maximum_external_cost=0,
        maximum_tool_cost=1.5,
    )
    assert len(provider.requests) == 1
    assert result.reserved_retrieval_cost == 1
    assert result.reserved_external_retrieval_cost == 0
    assert "CUMULATIVE_RETRIEVAL_COST_LIMIT" in " ".join(result.limitations)


@pytest.mark.asyncio
async def test_recommendation_budget_exhaustion_skips_third_model_call() -> None:
    request = research_request()
    request["execution_context"]["execution_budget"]["max_tokens"] = 20
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY), tokens=10),
            response(
                claim_payload(fact("evidence_internal_001")), tokens=10
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        request, existing_evidence=(evidence_item(),)
    )
    assert len(gateway.requests) == 2
    assert result.findings
    assert result.recommendations == ()
    assert "RECOMMENDATION_MODEL_BUDGET_EXHAUSTED" in result.limitations


@pytest.mark.asyncio
async def test_recommendation_cannot_express_approval_or_execution_authority() -> None:
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_internal_001"))),
            response(
                recommendation_payload(
                    finding_id=finding_id("claim_fact_001"),
                    action="Approve and deploy this technology automatically to production.",
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(), existing_evidence=(evidence_item(),)
    )
    assert result.findings
    assert result.recommendations == ()
    assert "RECOMMENDATION_AUTHORITY_SEMANTICS" in result.limitations


@pytest.mark.asyncio
async def test_generic_non_domain_recommendation_is_rejected() -> None:
    gateway = SequenceGateway(
        (
            response(plan_payload(ResearchDomain.TECHNOLOGY)),
            response(claim_payload(fact("evidence_internal_001"))),
            response(
                recommendation_payload(
                    finding_id=finding_id("claim_fact_001"),
                    action="Submit the cited material for human review and further discussion.",
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(), existing_evidence=(evidence_item(),)
    )
    assert result.findings
    assert result.recommendations == ()
    assert "RECOMMENDATION_DOMAIN_IRRELEVANT" in result.limitations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("domain", "action"),
    (
        (
            ResearchDomain.TECHNOLOGY,
            "Run a security and compatibility benchmark and submit PoC results for human review.",
        ),
        (
            ResearchDomain.PROPERTY_BUSINESS,
            "Run a pricing and unit economics scenario test for human commercial review.",
        ),
        (
            ResearchDomain.MANAGEMENT,
            "Draft an SOP and KPI control pilot for management review.",
        ),
        (
            ResearchDomain.PROPERTY_MARKET,
            "Run site due diligence and comparable sensitivity analysis for market review.",
        ),
    ),
)
async def test_four_domains_synthesize_substantive_recommendations(
    domain: ResearchDomain, action: str
) -> None:
    item = evidence_item(f"evidence_{domain.value.lower()}")
    gateway = SequenceGateway(
        (
            response(plan_payload(domain)),
            response(claim_payload(fact(item.evidence_id))),
            response(
                recommendation_payload(
                    finding_id=finding_id("claim_fact_001"),
                    evidence_ids=(item.evidence_id,),
                    action=action,
                )
            ),
        )
    )
    result = await make_orchestrator(gateway).orchestrate(
        research_request(domain), existing_evidence=(item,)
    )
    assert type(make_orchestrator(gateway)) is ResearchOrchestrator
    assert result.recommendations[0].proposed_action == action
    assert result.recommendations[0].requires_human_review is True
