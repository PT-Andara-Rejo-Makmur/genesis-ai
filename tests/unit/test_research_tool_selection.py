from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.research.decision import (
    EvidenceCandidate,
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchChannel,
    ResearchDecisionRequest,
    ResearchRisk,
)
from genesis.research.models import ResearchDomain
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.research.tool_selection import (
    AuthorizedResearchTool,
    ResearchToolCategory,
    ResearchToolSelectionKind,
    ResearchToolSelectionPolicy,
    ResearchToolSelectionRequest,
)
from genesis.runtime.context import DataClassification

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def decider() -> ExternalResearchDecider:
    return ExternalResearchDecider(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def evidence(*, channel: ResearchChannel = ResearchChannel.INTERNAL_SOURCE) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id="evidence_research_001",
        channel=channel,
        freshness=FreshnessStatus.CURRENT,
        reliability=SourceReliability.HIGH,
        scope_refs=("scope.research",),
        data_classification=DataClassification.INTERNAL,
    )


def decision_request(**changes: Any) -> ResearchDecisionRequest:
    value: dict[str, Any] = {
        "correlation_id": "corr_research_tool_001",
        "domain": ResearchDomain.TECHNOLOGY,
        "question": "What current evidence is required?",
        "risk": ResearchRisk.LOW,
        "data_classification": DataClassification.INTERNAL,
        "authorized_scope_refs": ("scope.research",),
        "authorized_permission_refs": ("research.external.read", "documents.read"),
        "allowed_tool_ids": ("research.external.retrieve", "documents.internal.search"),
        "evidence": (),
        "external": ExternalResearchBoundary(
            enabled=True,
            tool_id="research.external.retrieve",
            permission_ref="research.external.read",
            estimated_cost=1,
        ),
        "maximum_external_cost": 2,
    }
    value.update(changes)
    return ResearchDecisionRequest.model_validate(value)


def tool(
    tool_id: str,
    category: ResearchToolCategory,
    **changes: Any,
) -> AuthorizedResearchTool:
    value: dict[str, Any] = {
        "tool_id": tool_id,
        "category": category,
        "domains": tuple(ResearchDomain),
        "permission_refs": (),
        "scope_refs": ("scope.research",),
        "estimated_cost": 0,
    }
    value.update(changes)
    return AuthorizedResearchTool.model_validate(value)


def select(
    evidence_request: ResearchDecisionRequest,
    *tools: AuthorizedResearchTool,
):  # type: ignore[no-untyped-def]
    policy = ResearchToolSelectionPolicy(evidence_decider=decider())
    return policy.select(
        ResearchToolSelectionRequest(
            evidence_request=evidence_request,
            available_tools=tools,
        )
    )


@pytest.mark.parametrize("domain", list(ResearchDomain))
def test_all_domains_use_one_generic_selector(domain: ResearchDomain) -> None:
    external = tool(
        "research.external.retrieve",
        ResearchToolCategory.EXTERNAL_RESEARCH,
        permission_refs=("research.external.read",),
        estimated_cost=1,
    )
    result = select(decision_request(domain=domain), external)
    assert result.kind is ResearchToolSelectionKind.SELECT_TOOL
    assert result.domain is domain
    assert result.selected_tool_id == "research.external.retrieve"
    assert result.instruction_authority is False


def test_internal_current_evidence_is_preferred_without_tool() -> None:
    result = select(
        decision_request(evidence=(evidence(),)),
        tool("research.external.retrieve", ResearchToolCategory.EXTERNAL_RESEARCH),
    )
    assert result.kind is ResearchToolSelectionKind.USE_EXISTING_EVIDENCE
    assert result.selected_evidence_ids == ("evidence_research_001",)
    assert result.selected_tool_id is None


def test_memory_is_used_only_under_existing_risk_policy() -> None:
    memory = evidence(channel=ResearchChannel.MEMORY)
    low = select(decision_request(evidence=(memory,), risk=ResearchRisk.LOW))
    high = select(
        decision_request(evidence=(memory,), risk=ResearchRisk.HIGH),
        tool(
            "research.external.retrieve",
            ResearchToolCategory.EXTERNAL_RESEARCH,
            permission_refs=("research.external.read",),
            estimated_cost=1,
        ),
    )
    assert low.kind is ResearchToolSelectionKind.USE_EXISTING_EVIDENCE
    assert high.kind is ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE


def test_authorized_internal_retrieval_precedes_external_escalation() -> None:
    internal = tool("documents.internal.search", ResearchToolCategory.INTERNAL_DOCUMENT)
    external = tool(
        "research.external.retrieve",
        ResearchToolCategory.EXTERNAL_RESEARCH,
        permission_refs=("research.external.read",),
        estimated_cost=1,
    )
    result = select(decision_request(), internal, external)
    assert result.selected_tool_id == "documents.internal.search"
    assert result.selected_category is ResearchToolCategory.INTERNAL_DOCUMENT
    assert "AUTHORIZED_EVIDENCE_GAP_TOOL" in result.reason_codes


def test_external_is_selected_only_when_governed_options_are_exhausted() -> None:
    external = tool(
        "research.external.retrieve",
        ResearchToolCategory.EXTERNAL_RESEARCH,
        permission_refs=("research.external.read",),
        estimated_cost=1,
    )
    result = select(decision_request(), external)
    assert result.selected_tool_id == "research.external.retrieve"
    assert result.selected_category is ResearchToolCategory.EXTERNAL_RESEARCH
    assert "EXTERNAL_RESEARCH_GAP_AUTHORIZED" in result.reason_codes


@pytest.mark.parametrize(
    "change",
    [
        {"allowed_tool_ids": ()},
        {"authorized_permission_refs": ()},
        {"maximum_external_cost": 0.5},
        {"external": ExternalResearchBoundary(enabled=False)},
    ],
)
def test_external_unavailable_unauthorized_or_over_cost_is_not_selected(
    change: dict[str, Any],
) -> None:
    external = tool(
        "research.external.retrieve",
        ResearchToolCategory.EXTERNAL_RESEARCH,
        permission_refs=("research.external.read",),
        estimated_cost=1,
    )
    result = select(decision_request(**change), external)
    assert result.kind is ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE
    assert result.selected_tool_id is None


def test_caller_supplied_internal_tool_can_fill_gap_when_external_disabled() -> None:
    internal = tool(
        "documents.internal.search",
        ResearchToolCategory.INTERNAL_DOCUMENT,
        permission_refs=("documents.read",),
    )
    result = select(decision_request(external=ExternalResearchBoundary(enabled=False)), internal)
    assert result.kind is ResearchToolSelectionKind.SELECT_TOOL
    assert result.selected_category is ResearchToolCategory.INTERNAL_DOCUMENT


def test_external_cost_ceiling_does_not_reject_non_external_categories() -> None:
    internal = tool(
        "documents.internal.search",
        ResearchToolCategory.INTERNAL_DOCUMENT,
        estimated_cost=5,
    )
    result = select(
        decision_request(
            maximum_external_cost=0,
            external=ExternalResearchBoundary(enabled=False),
        ),
        internal,
    )
    assert result.kind is ResearchToolSelectionKind.SELECT_TOOL
    assert result.selected_tool_id == "documents.internal.search"


def test_explicit_generic_tool_cost_ceiling_applies_to_all_categories() -> None:
    request = ResearchToolSelectionRequest(
        evidence_request=decision_request(
            maximum_external_cost=0,
            external=ExternalResearchBoundary(enabled=False),
        ),
        available_tools=(
            tool(
                "documents.internal.search",
                ResearchToolCategory.INTERNAL_DOCUMENT,
                estimated_cost=5,
            ),
        ),
        maximum_tool_cost=4,
    )
    result = ResearchToolSelectionPolicy(evidence_decider=decider()).select(request)
    assert result.kind is ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("domain", "expected"),
    (
        (ResearchDomain.TECHNOLOGY, "documents.internal.search"),
        (ResearchDomain.PROPERTY_BUSINESS, "documents.internal.search"),
        (ResearchDomain.MANAGEMENT, "documents.internal.search"),
        (ResearchDomain.PROPERTY_MARKET, "datasets.public.market"),
    ),
)
def test_domain_preferences_choose_among_governed_categories(
    domain: ResearchDomain, expected: str
) -> None:
    request = decision_request(
        domain=domain,
        allowed_tool_ids=(
            "documents.internal.search",
            "datasets.public.market",
            "connector.authorized",
            "research.external.retrieve",
        ),
    )
    result = select(
        request,
        tool("documents.internal.search", ResearchToolCategory.INTERNAL_DOCUMENT),
        tool("datasets.public.market", ResearchToolCategory.PUBLIC_DATASET),
        tool("connector.authorized", ResearchToolCategory.CONNECTOR),
        tool(
            "research.external.retrieve",
            ResearchToolCategory.EXTERNAL_RESEARCH,
            permission_refs=("research.external.read",),
            estimated_cost=1,
        ),
    )
    assert result.selected_tool_id == expected


def test_property_market_prefers_fresh_public_dataset_category() -> None:
    request = decision_request(
        domain=ResearchDomain.PROPERTY_MARKET,
        external=ExternalResearchBoundary(enabled=False),
        allowed_tool_ids=("documents.internal.search", "datasets.public.market"),
    )
    result = select(
        request,
        tool("documents.internal.search", ResearchToolCategory.INTERNAL_DOCUMENT),
        tool("datasets.public.market", ResearchToolCategory.PUBLIC_DATASET),
    )
    assert result.selected_tool_id == "datasets.public.market"


def test_scope_domain_permission_and_restricted_guards_are_fail_closed() -> None:
    forbidden = (
        tool(
            "documents.internal.search",
            ResearchToolCategory.INTERNAL_DOCUMENT,
            scope_refs=("scope.other",),
        ),
        tool(
            "documents.internal.search",
            ResearchToolCategory.INTERNAL_DOCUMENT,
            domains=(ResearchDomain.MANAGEMENT,),
        ),
        tool(
            "documents.internal.search",
            ResearchToolCategory.INTERNAL_DOCUMENT,
            permission_refs=("documents.admin",),
        ),
    )
    base = decision_request(external=ExternalResearchBoundary(enabled=False))
    assert all(
        select(base, item).kind is ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE
        for item in forbidden
    )

    restricted = decision_request(
        data_classification=DataClassification.RESTRICTED,
        external=ExternalResearchBoundary(enabled=False),
    )
    unsafe = tool("documents.internal.search", ResearchToolCategory.INTERNAL_DOCUMENT)
    safe = unsafe.model_copy(update={"supports_restricted": True})
    assert select(restricted, unsafe).kind is ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE
    assert select(restricted, safe).kind is ResearchToolSelectionKind.SELECT_TOOL


def test_incomplete_question_never_selects_tool() -> None:
    result = select(
        decision_request(information_complete=False),
        tool("documents.internal.search", ResearchToolCategory.INTERNAL_DOCUMENT),
    )
    assert result.kind is ResearchToolSelectionKind.NEEDS_INFO
