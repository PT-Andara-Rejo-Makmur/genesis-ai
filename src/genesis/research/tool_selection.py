"""Shared, deterministic R&D tool-category selection under current authority."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from genesis.research.decision import (
    ExternalResearchDecider,
    ResearchDecisionKind,
    ResearchDecisionRequest,
    ResearchRisk,
)
from genesis.research.models import ResearchDomain
from genesis.runtime.context import DataClassification


class ResearchToolCategory(StrEnum):
    INTERNAL_DOCUMENT = "INTERNAL_DOCUMENT"
    MEMORY = "MEMORY"
    EXTERNAL_RESEARCH = "EXTERNAL_RESEARCH"
    PUBLIC_DATASET = "PUBLIC_DATASET"
    CONNECTOR = "CONNECTOR"


class ResearchToolSelectionKind(StrEnum):
    USE_EXISTING_EVIDENCE = "USE_EXISTING_EVIDENCE"
    SELECT_TOOL = "SELECT_TOOL"
    NEEDS_INFO = "NEEDS_INFO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AuthorizedResearchTool(BaseModel):
    """Caller-supplied descriptor; it does not register or authorize a tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tool_id: str = Field(min_length=3, max_length=128)
    category: ResearchToolCategory
    domains: tuple[ResearchDomain, ...] = Field(min_length=1)
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)
    estimated_cost: float = Field(default=0, ge=0)
    supports_restricted: bool = False


class ResearchToolSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_request: ResearchDecisionRequest
    available_tools: tuple[AuthorizedResearchTool, ...] = ()
    maximum_tool_cost: float | None = Field(default=None, ge=0)


class ResearchToolSelectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: ResearchToolSelectionKind
    domain: ResearchDomain
    selected_tool_id: str | None = None
    selected_category: ResearchToolCategory | None = None
    selected_evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = Field(min_length=1)
    instruction_authority: bool = False


_DOMAIN_PREFERENCES: dict[ResearchDomain, tuple[ResearchToolCategory, ...]] = {
    ResearchDomain.TECHNOLOGY: (
        ResearchToolCategory.INTERNAL_DOCUMENT,
        ResearchToolCategory.CONNECTOR,
        ResearchToolCategory.PUBLIC_DATASET,
        ResearchToolCategory.EXTERNAL_RESEARCH,
    ),
    ResearchDomain.PROPERTY_BUSINESS: (
        ResearchToolCategory.INTERNAL_DOCUMENT,
        ResearchToolCategory.CONNECTOR,
        ResearchToolCategory.PUBLIC_DATASET,
        ResearchToolCategory.EXTERNAL_RESEARCH,
    ),
    ResearchDomain.MANAGEMENT: (
        ResearchToolCategory.INTERNAL_DOCUMENT,
        ResearchToolCategory.CONNECTOR,
        ResearchToolCategory.EXTERNAL_RESEARCH,
        ResearchToolCategory.PUBLIC_DATASET,
    ),
    ResearchDomain.PROPERTY_MARKET: (
        ResearchToolCategory.PUBLIC_DATASET,
        ResearchToolCategory.INTERNAL_DOCUMENT,
        ResearchToolCategory.CONNECTOR,
        ResearchToolCategory.EXTERNAL_RESEARCH,
    ),
}


class ResearchToolSelectionPolicy:
    """Use ExternalResearchDecider, then select only a supplied authorized tool."""

    def __init__(self, *, evidence_decider: ExternalResearchDecider) -> None:
        self._evidence_decider = evidence_decider

    def select(self, request: ResearchToolSelectionRequest) -> ResearchToolSelectionDecision:
        evidence = self._evidence_decider.decide(request.evidence_request)
        domain = request.evidence_request.domain
        if evidence.decision in {
            ResearchDecisionKind.USE_INTERNAL_SOURCE,
            ResearchDecisionKind.USE_MEMORY,
        }:
            return ResearchToolSelectionDecision(
                kind=ResearchToolSelectionKind.USE_EXISTING_EVIDENCE,
                domain=domain,
                selected_evidence_ids=evidence.selected_evidence_ids,
                reason_codes=(evidence.decision.value,),
            )
        if evidence.decision is ResearchDecisionKind.NEEDS_INFORMATION:
            return ResearchToolSelectionDecision(
                kind=ResearchToolSelectionKind.NEEDS_INFO,
                domain=domain,
                reason_codes=("QUESTION_INFORMATION_INCOMPLETE",),
            )

        candidates = self._eligible_tools(request)
        governed = [
            item
            for item in candidates
            if item.category is not ResearchToolCategory.EXTERNAL_RESEARCH
        ]
        if governed:
            candidates = governed
            reason = "AUTHORIZED_EVIDENCE_GAP_TOOL"
        elif evidence.decision is ResearchDecisionKind.REQUEST_EXTERNAL_RESEARCH:
            proposal_id = evidence.retrieval.tool_id if evidence.retrieval is not None else None
            candidates = [
                item
                for item in candidates
                if item.tool_id == proposal_id
                and item.category is ResearchToolCategory.EXTERNAL_RESEARCH
            ]
            reason = "EXTERNAL_RESEARCH_GAP_AUTHORIZED"
        else:
            candidates = []
            reason = "AUTHORIZED_EVIDENCE_GAP_TOOL"

        if not candidates:
            return ResearchToolSelectionDecision(
                kind=ResearchToolSelectionKind.INSUFFICIENT_EVIDENCE,
                domain=domain,
                reason_codes=("NO_AUTHORIZED_COST_SAFE_TOOL", evidence.decision.value),
            )
        preference = _DOMAIN_PREFERENCES[domain]
        selected = sorted(
            candidates,
            key=lambda item: (
                preference.index(item.category),
                item.estimated_cost,
                item.tool_id,
            ),
        )[0]
        return ResearchToolSelectionDecision(
            kind=ResearchToolSelectionKind.SELECT_TOOL,
            domain=domain,
            selected_tool_id=selected.tool_id,
            selected_category=selected.category,
            reason_codes=(reason, f"DOMAIN_{domain.value}", "AUTHORITY_AND_COST_VERIFIED"),
        )

    @staticmethod
    def _eligible_tools(
        request: ResearchToolSelectionRequest,
    ) -> list[AuthorizedResearchTool]:
        evidence = request.evidence_request
        allowed = set(evidence.allowed_tool_ids)
        permissions = set(evidence.authorized_permission_refs)
        scopes = set(evidence.authorized_scope_refs)
        result: list[AuthorizedResearchTool] = []
        for item in request.available_tools:
            if item.tool_id not in allowed or evidence.domain not in item.domains:
                continue
            if not set(item.permission_refs).issubset(permissions):
                continue
            if not set(item.scope_refs).issubset(scopes):
                continue
            if (
                request.maximum_tool_cost is not None
                and item.estimated_cost > request.maximum_tool_cost
            ):
                continue
            if (
                item.category is ResearchToolCategory.EXTERNAL_RESEARCH
                and item.estimated_cost > evidence.maximum_external_cost
            ):
                continue
            if (
                evidence.data_classification is DataClassification.RESTRICTED
                and not item.supports_restricted
            ):
                continue
            if evidence.risk in {ResearchRisk.HIGH, ResearchRisk.CRITICAL} and item.category in {
                ResearchToolCategory.EXTERNAL_RESEARCH,
                ResearchToolCategory.PUBLIC_DATASET,
            }:
                continue
            result.append(item)
        return result
