"""Traceable research-source selection without retrieval or authority expansion."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.research.domains import ResearchDomainProfile, domain_profile
from genesis.research.models import ResearchDomain
from genesis.research.sources import FreshnessStatus, SourceReliability
from genesis.runtime.context import DataClassification

RESEARCH_DECISION_SCHEMA = "https://schemas.alos.dev/v1/research/research-decision.schema.json"


class ResearchChannel(StrEnum):
    INTERNAL_SOURCE = "INTERNAL_SOURCE"
    MEMORY = "MEMORY"


class ResearchDecisionKind(StrEnum):
    USE_INTERNAL_SOURCE = "USE_INTERNAL_SOURCE"
    USE_MEMORY = "USE_MEMORY"
    REQUEST_EXTERNAL_RESEARCH = "REQUEST_EXTERNAL_RESEARCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"


class ResearchRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str = Field(min_length=3, max_length=128)
    channel: ResearchChannel
    freshness: FreshnessStatus
    reliability: SourceReliability
    available: bool = True
    scope_refs: tuple[str, ...] = Field(min_length=1)
    data_classification: DataClassification


class ExternalResearchBoundary(BaseModel):
    """Backend-governed retrieval proposal; this model performs no HTTP access."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = False
    tool_id: str = Field(default="research.external.retrieve", min_length=3, max_length=128)
    permission_ref: str = Field(default="research.external.read", min_length=3, max_length=128)
    estimated_cost: float = Field(default=0, ge=0)


class ResearchDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    correlation_id: str = Field(min_length=3, max_length=128)
    domain: ResearchDomain
    question: str = Field(min_length=1)
    risk: ResearchRisk
    data_classification: DataClassification
    authorized_scope_refs: tuple[str, ...] = Field(min_length=1)
    authorized_permission_refs: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceCandidate, ...] = ()
    information_complete: bool = True
    external: ExternalResearchBoundary = ExternalResearchBoundary()
    maximum_external_cost: float = Field(default=0, ge=0)


class BackendRetrievalProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    boundary: Literal["BACKEND_TOOL_EXECUTOR"] = "BACKEND_TOOL_EXECUTOR"
    tool_id: str
    instruction_authority: Literal[False] = False
    permission_expansion: Literal[False] = False
    scope_expansion: Literal[False] = False


class ResearchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    correlation_id: str
    decision: ResearchDecisionKind
    domain_profile: ResearchDomainProfile
    selected_evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...] = Field(min_length=1)
    authorized_scope_refs: tuple[str, ...]
    authorized_permission_refs: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]
    retrieval: BackendRetrievalProposal | None = None
    external_content_trust: Literal["UNTRUSTED"] = "UNTRUSTED"
    canonical_research_decision: dict[str, Any] = Field(exclude=True)

    def as_canonical(self) -> dict[str, Any]:
        """Return only the contract-valid cross-service projection."""

        return dict(self.canonical_research_decision)


class ResearchDecisionFailure(Exception):
    def __init__(self, code: str, message: str, correlation_id: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.correlation_id = correlation_id

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "code": self.code,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "retryable": False,
        }


class ExternalResearchDecider:
    """Prefer authorized internal evidence, then memory, then Backend retrieval."""

    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def decide(self, request: ResearchDecisionRequest) -> ResearchDecision:
        self._validate_evidence_scope(request)
        profile = domain_profile(request.domain)
        if not request.information_complete:
            return self._result(
                request,
                profile,
                ResearchDecisionKind.NEEDS_INFORMATION,
                (),
                ("The task is missing information required to define the evidence need.",),
            )

        current = tuple(
            item
            for item in request.evidence
            if item.available
            and item.freshness is FreshnessStatus.CURRENT
            and item.reliability not in {SourceReliability.UNVERIFIED, SourceReliability.LOW}
        )
        internal = tuple(
            item for item in current if item.channel is ResearchChannel.INTERNAL_SOURCE
        )
        if internal:
            return self._result(
                request,
                profile,
                ResearchDecisionKind.USE_INTERNAL_SOURCE,
                tuple(item.evidence_id for item in internal),
                ("Current authorized internal evidence satisfies the evidence need.",),
            )
        memory = tuple(item for item in current if item.channel is ResearchChannel.MEMORY)
        if memory and request.risk in {ResearchRisk.LOW, ResearchRisk.MEDIUM}:
            return self._result(
                request,
                profile,
                ResearchDecisionKind.USE_MEMORY,
                tuple(item.evidence_id for item in memory),
                ("Current authorized memory satisfies the bounded evidence need.",),
            )

        stale = sorted(
            item.evidence_id
            for item in request.evidence
            if item.freshness is not FreshnessStatus.CURRENT
        )
        reasons = ["No current authorized internal evidence or sufficient memory is available."]
        if stale:
            reasons.append("Stale or unknown evidence was excluded: " + ", ".join(stale))
        external_denial = self._external_denial(request)
        if external_denial is None:
            reasons.append("External evidence retrieval is required and authorized via Backend.")
            return self._result(
                request,
                profile,
                ResearchDecisionKind.REQUEST_EXTERNAL_RESEARCH,
                (),
                tuple(reasons),
                retrieval=BackendRetrievalProposal(tool_id=request.external.tool_id),
            )
        reasons.append(external_denial)
        return self._result(
            request,
            profile,
            ResearchDecisionKind.INSUFFICIENT_EVIDENCE,
            (),
            tuple(reasons),
        )

    @staticmethod
    def _validate_evidence_scope(request: ResearchDecisionRequest) -> None:
        authorized = set(request.authorized_scope_refs)
        classification_rank = {
            DataClassification.PUBLIC: 0,
            DataClassification.INTERNAL: 1,
            DataClassification.CONFIDENTIAL: 2,
            DataClassification.RESTRICTED: 3,
        }
        for item in request.evidence:
            if not set(item.scope_refs).issubset(authorized):
                raise ResearchDecisionFailure(
                    "RESEARCH_EVIDENCE_SCOPE_DENIED",
                    "Evidence is outside the Backend-authorized research scope.",
                    request.correlation_id,
                )
            if (
                classification_rank[item.data_classification]
                > classification_rank[request.data_classification]
            ):
                raise ResearchDecisionFailure(
                    "RESEARCH_EVIDENCE_CLASSIFICATION_DENIED",
                    "Evidence classification exceeds the authorized research context.",
                    request.correlation_id,
                )

    @staticmethod
    def _external_denial(request: ResearchDecisionRequest) -> str | None:
        if not request.external.enabled:
            return "External research is disabled by the Backend boundary."
        if request.data_classification is DataClassification.RESTRICTED:
            return "Restricted context cannot be sent to external retrieval."
        if request.external.tool_id not in request.allowed_tool_ids:
            return "The external retrieval tool is not in the Backend allowlist."
        if request.external.permission_ref not in request.authorized_permission_refs:
            return "The actor lacks the Backend-authorized external research permission."
        if request.external.estimated_cost > request.maximum_external_cost:
            return "External retrieval exceeds the authorized cost budget."
        return None

    def _result(
        self,
        request: ResearchDecisionRequest,
        profile: ResearchDomainProfile,
        decision: ResearchDecisionKind,
        evidence_ids: tuple[str, ...],
        reasons: tuple[str, ...],
        *,
        retrieval: BackendRetrievalProposal | None = None,
    ) -> ResearchDecision:
        canonical = {
            "correlation_id": request.correlation_id,
            "decision": decision.value,
            "domain": request.domain.value,
            "selected_evidence_ids": list(evidence_ids),
            "reasons": list(reasons),
            "retrieval": (retrieval.model_dump(mode="json") if retrieval is not None else None),
            "external_content_trust": "UNTRUSTED",
        }
        try:
            validated = self._contracts.validate(RESEARCH_DECISION_SCHEMA, canonical)
        except (ContractValidationError, ValueError) as exc:
            raise ResearchDecisionFailure(
                "RESEARCH_DECISION_CONTRACT_INVALID",
                "Research decision does not satisfy the canonical contract.",
                request.correlation_id,
            ) from exc
        return ResearchDecision(
            correlation_id=request.correlation_id,
            decision=decision,
            domain_profile=profile,
            selected_evidence_ids=evidence_ids,
            reasons=reasons,
            authorized_scope_refs=request.authorized_scope_refs,
            authorized_permission_refs=request.authorized_permission_refs,
            allowed_tool_ids=request.allowed_tool_ids,
            retrieval=retrieval,
            canonical_research_decision=validated,
        )
