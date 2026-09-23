"""Internal delegation projections; none of these models are canonical contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.research.models import ResearchDomain
from genesis.research.tool_selection import ResearchToolCategory
from genesis.runtime.context import DataClassification
from genesis.runtime.limits import ExecutionBudget


class AuthorityEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3)
    organization_id: str = Field(min_length=3)
    workspace_id: str = Field(min_length=3)
    permission_refs: frozenset[str] = frozenset()
    scope_refs: frozenset[str] = Field(min_length=1)
    allowed_tool_ids: frozenset[str] = frozenset()
    data_classification: DataClassification


class AuthorizedChildTarget(BaseModel):
    """Backend/caller supplied visibility; this does not authorize execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: str = Field(min_length=3)
    agent_version: str = Field(min_length=1)
    capability_ids: tuple[str, ...] = Field(min_length=1)
    research_domains: tuple[ResearchDomain, ...] = ()
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    @property
    def exact_ref(self) -> str:
        return f"{self.agent_id}@{self.agent_version}"


class ChildTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    child_task_id: str = Field(min_length=3)
    goal: str = Field(min_length=1)
    input: dict[str, Any]
    expected_result_schema: dict[str, Any]
    evidence_expectations: tuple[str, ...] = ()
    domain: ResearchDomain | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchDelegationConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    allowed_domains: frozenset[ResearchDomain] = frozenset()
    allowed_source_categories: frozenset[ResearchToolCategory] = frozenset()
    external_research_allowed: bool = False
    maximum_external_cost: float = Field(default=0, ge=0)
    data_classification_ceiling: DataClassification

    @model_validator(mode="after")
    def enforce_external_egress_consistency(self) -> ResearchDelegationConstraints:
        external_category = ResearchToolCategory.EXTERNAL_RESEARCH
        if (
            not self.external_research_allowed
            and external_category in self.allowed_source_categories
        ):
            raise ValueError("EXTERNAL_RESEARCH category requires external research permission")
        if not self.external_research_allowed and self.maximum_external_cost != 0:
            raise ValueError("Disabled external research requires zero external cost")
        return self


class ChildAuthorityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    authority: AuthorityEnvelope
    budget: ExecutionBudget
    research_constraints: ResearchDelegationConstraints | None = None


class DelegationIntent(BaseModel):
    """A non-authoritative proposal submitted to the Backend delegation boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    parent_run_id: str = Field(min_length=3)
    root_run_id: str = Field(min_length=3)
    parent_agent_id: str = Field(min_length=3)
    parent_agent_version: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=3)
    target_agent_version: str = Field(min_length=1)
    target_capability_id: str = Field(min_length=3)
    depth: int = Field(ge=1)
    ancestry_agent_refs: tuple[str, ...]
    task: ChildTaskSpec
    requested_authority: ChildAuthorityRequest
    delegation_key: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class DelegationProposal(BaseModel):
    """Strict model/planner proposal; runtime derives lineage and deterministic identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    target_agent_id: str = Field(min_length=3)
    target_agent_version: str = Field(min_length=1)
    target_capability_id: str = Field(min_length=3)
    task: ChildTaskSpec
    requested_authority: ChildAuthorityRequest


class DelegationAuthorizationSnapshot(BaseModel):
    """Backend-issued parent bounds consumed only for local fail-closed preflight."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = False
    parent_run_id: str = Field(min_length=3)
    root_run_id: str = Field(min_length=3)
    parent_agent_id: str = Field(min_length=3)
    parent_agent_version: str = Field(min_length=1)
    parent_depth: int = Field(ge=0)
    ancestry_agent_refs: tuple[str, ...]
    allowed_child_targets: tuple[AuthorizedChildTarget, ...] = ()
    max_depth: int = Field(ge=0)
    max_children: int = Field(ge=0)
    concurrency_preflight_limit: int | None = Field(default=None, ge=1)
    effective_parent_authority: AuthorityEnvelope
    parent_budget: ExecutionBudget
    research_constraints: ResearchDelegationConstraints | None = None


class ChildObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    child_task_id: str
    delegation_key: str
    target_agent_id: str
    target_agent_version: str
    target_capability_id: str
    run_id: str | None = None
    status: Literal["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]
    validation_status: Literal["VALID", "INVALID"]
    output: Any = None
    evidence_refs: tuple[dict[str, Any], ...] = ()
    usage: dict[str, Any] | None = None
    error_code: str | None = None


class DelegationDisposition(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DelegationSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    disposition: DelegationDisposition
    successful_children: tuple[ChildObservation, ...]
    failed_children: tuple[ChildObservation, ...]
    evidence_refs: tuple[dict[str, Any], ...]
    reason_codes: tuple[str, ...] = Field(min_length=1)


class DomainDelegationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    child_task_id: str
    domain: ResearchDomain
    goal: str = Field(min_length=1)
    input: dict[str, Any]
    expected_result_schema: dict[str, Any]
    authority: ChildAuthorityRequest
    capability_id: str
