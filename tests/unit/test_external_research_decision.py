from __future__ import annotations

from pathlib import Path

import pytest

from genesis.contracts import CanonicalContractCatalog
from genesis.research import (
    EvidenceCandidate,
    ExternalResearchBoundary,
    ExternalResearchDecider,
    ResearchChannel,
    ResearchDecisionFailure,
    ResearchDecisionKind,
    ResearchDecisionRequest,
    ResearchDomain,
    ResearchRisk,
)
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.runtime.context import DataClassification

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"


def decider() -> ExternalResearchDecider:
    return ExternalResearchDecider(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def evidence(**changes: object) -> EvidenceCandidate:
    value: dict[str, object] = {
        "evidence_id": "evidence_internal_001",
        "channel": ResearchChannel.INTERNAL_SOURCE,
        "freshness": FreshnessStatus.CURRENT,
        "reliability": SourceReliability.HIGH,
        "available": True,
        "scope_refs": ["scope.project.genesis"],
        "data_classification": DataClassification.INTERNAL,
    }
    value.update(changes)
    return EvidenceCandidate.model_validate(value)


def request(**changes: object) -> ResearchDecisionRequest:
    value: dict[str, object] = {
        "correlation_id": "corr_research_decision_001",
        "domain": ResearchDomain.TECHNOLOGY,
        "question": "Which supported architecture is appropriate?",
        "risk": ResearchRisk.MEDIUM,
        "data_classification": DataClassification.INTERNAL,
        "authorized_scope_refs": ["scope.project.genesis"],
        "authorized_permission_refs": ["research.external.read"],
        "allowed_tool_ids": ["research.external.retrieve"],
        "evidence": [evidence()],
        "external": ExternalResearchBoundary(
            enabled=True,
            tool_id="research.external.retrieve",
            permission_ref="research.external.read",
            estimated_cost=1.0,
        ),
        "maximum_external_cost": 2.0,
    }
    value.update(changes)
    return ResearchDecisionRequest.model_validate(value)


def test_valid_internal_only_request_uses_internal_source() -> None:
    result = decider().decide(
        request(external=ExternalResearchBoundary(enabled=False))
    )

    assert result.decision is ResearchDecisionKind.USE_INTERNAL_SOURCE
    assert result.selected_evidence_ids == ("evidence_internal_001",)
    assert result.retrieval is None
    assert result.correlation_id == "corr_research_decision_001"


def test_external_research_is_required_only_through_backend_boundary() -> None:
    result = decider().decide(request(evidence=[]))

    assert result.decision is ResearchDecisionKind.REQUEST_EXTERNAL_RESEARCH
    assert result.retrieval is not None
    assert result.retrieval.boundary == "BACKEND_TOOL_EXECUTOR"
    assert result.retrieval.tool_id == "research.external.retrieve"
    assert result.retrieval.permission_expansion is False
    assert result.external_content_trust == "UNTRUSTED"
    assert result.as_canonical() == {
        "correlation_id": "corr_research_decision_001",
        "decision": "REQUEST_EXTERNAL_RESEARCH",
        "domain": "TECHNOLOGY",
        "selected_evidence_ids": [],
        "reasons": list(result.reasons),
        "retrieval": {
            "boundary": "BACKEND_TOOL_EXECUTOR",
            "tool_id": "research.external.retrieve",
            "instruction_authority": False,
            "permission_expansion": False,
            "scope_expansion": False,
        },
        "external_content_trust": "UNTRUSTED",
    }
    assert "authorized_permission_refs" not in result.as_canonical()
    assert "canonical_research_decision" not in result.model_dump(mode="json")


def test_external_research_is_not_required_when_memory_is_sufficient() -> None:
    memory = evidence(
        evidence_id="memory_evidence_001",
        channel=ResearchChannel.MEMORY,
    )
    result = decider().decide(request(evidence=[memory]))

    assert result.decision is ResearchDecisionKind.USE_MEMORY
    assert result.retrieval is None


def test_stale_evidence_and_disabled_external_return_insufficient_evidence() -> None:
    stale = evidence(freshness=FreshnessStatus.STALE)
    result = decider().decide(
        request(evidence=[stale], external=ExternalResearchBoundary(enabled=False))
    )

    assert result.decision is ResearchDecisionKind.INSUFFICIENT_EVIDENCE
    assert "evidence_internal_001" in " ".join(result.reasons)
    assert result.correlation_id == "corr_research_decision_001"


def test_missing_task_information_returns_needs_information() -> None:
    result = decider().decide(request(information_complete=False))
    assert result.decision is ResearchDecisionKind.NEEDS_INFORMATION


def test_external_research_cannot_expand_tool_permission_or_cost_authority() -> None:
    no_tool = decider().decide(request(evidence=[], allowed_tool_ids=[]))
    assert no_tool.decision is ResearchDecisionKind.INSUFFICIENT_EVIDENCE

    no_permission = decider().decide(
        request(evidence=[], authorized_permission_refs=[])
    )
    assert no_permission.decision is ResearchDecisionKind.INSUFFICIENT_EVIDENCE

    over_cost = decider().decide(
        request(evidence=[], maximum_external_cost=0.5)
    )
    assert over_cost.decision is ResearchDecisionKind.INSUFFICIENT_EVIDENCE


def test_cross_scope_evidence_fails_closed_and_preserves_correlation() -> None:
    cross_scope = evidence(scope_refs=["scope.project.other"])
    with pytest.raises(ResearchDecisionFailure) as raised:
        decider().decide(request(evidence=[cross_scope]))

    assert raised.value.code == "RESEARCH_EVIDENCE_SCOPE_DENIED"
    assert raised.value.correlation_id == "corr_research_decision_001"


def test_four_domains_are_profiles_not_authorization_mechanisms() -> None:
    decisions = [
        decider().decide(request(domain=domain)) for domain in ResearchDomain
    ]

    assert {result.domain_profile.domain for result in decisions} == set(ResearchDomain)
    assert {result.authorized_scope_refs for result in decisions} == {
        ("scope.project.genesis",)
    }
    assert {result.authorized_permission_refs for result in decisions} == {
        ("research.external.read",)
    }
    assert {result.allowed_tool_ids for result in decisions} == {
        ("research.external.retrieve",)
    }
