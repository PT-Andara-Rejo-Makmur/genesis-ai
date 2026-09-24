"""Internal, non-authoritative workforce planning models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.capabilities.resolver import CapabilityCatalogItem
from genesis.control_plane.factory import (
    FactoryAnalysisResult,
    FactoryRequirement,
)
from genesis.runtime.limits import ExecutionBudget


class DependencyKind(StrEnum):
    CAPABILITY = "CAPABILITY"
    SKILL = "SKILL"
    TOOL = "TOOL"
    PERMISSION = "PERMISSION"
    SCOPE = "SCOPE"
    MODEL_POLICY = "MODEL_POLICY"
    BUDGET_POLICY = "BUDGET_POLICY"
    DELEGATION_POLICY = "DELEGATION_POLICY"
    EVIDENCE = "EVIDENCE"


class DependencyStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    REUSED = "REUSED"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    NEEDS_CONFIGURATION = "NEEDS_CONFIGURATION"


class EvaluationKind(StrEnum):
    FUNCTIONAL = "FUNCTIONAL"
    PERMISSION_SCOPE = "PERMISSION_SCOPE"
    TOOL_BEHAVIOR = "TOOL_BEHAVIOR"
    EVIDENCE = "EVIDENCE"
    BUDGET = "BUDGET"
    DELEGATION = "DELEGATION"
    SAFE_FAILURE = "SAFE_FAILURE"
    DUPLICATION = "DUPLICATION"
    REGRESSION = "REGRESSION"


class AssuranceCode(StrEnum):
    DUPLICATE_CAPABILITY = "DUPLICATE_CAPABILITY"
    DUPLICATE_RESPONSIBILITY = "DUPLICATE_RESPONSIBILITY"
    GRAPH_CYCLE = "GRAPH_CYCLE"
    ORPHAN_NODE = "ORPHAN_NODE"
    INVALID_HIERARCHY = "INVALID_HIERARCHY"
    CHILD_BROADER_THAN_PARENT = "CHILD_BROADER_THAN_PARENT"
    CHILD_PERMISSION_EXPANSION = "CHILD_PERMISSION_EXPANSION"
    CHILD_SCOPE_EXPANSION = "CHILD_SCOPE_EXPANSION"
    INVENTED_AVAILABLE_DEPENDENCY = "INVENTED_AVAILABLE_DEPENDENCY"
    MISSING_EVALUATION_COVERAGE = "MISSING_EVALUATION_COVERAGE"


class ResponsibilityRequirement(BaseModel):
    """Optional structured hint used by deterministic tests or upstream interpreters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: str = Field(min_length=3, max_length=128)
    purpose: str = Field(min_length=1)
    parent_identity: str | None = Field(default=None, min_length=3, max_length=128)
    atomic: bool = True
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    required_skill_ids: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] | None = None
    scope_refs: tuple[str, ...] | None = None


class DelegationPolicyRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    max_depth: int = Field(default=2, ge=0, le=8)
    max_children: int = Field(default=8, ge=0)
    scope_inheritance_required: Literal[True] = True
    permission_inheritance_required: Literal[True] = True


class WorkforceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement: FactoryRequirement
    responsibility_hints: tuple[ResponsibilityRequirement, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    required_skill_ids: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    model_policy_ref: str | None = Field(default=None, min_length=1)
    budget_policy: ExecutionBudget | None = None
    delegation_policy: DelegationPolicyRequirement = DelegationPolicyRequirement()
    evidence_requirements: tuple[str, ...] = (
        "Material conclusions cite immutable evidence or Backend ToolResult references.",
    )


class InterpretedResponsibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: str
    purpose: str
    parent_identity: str | None = None
    atomic: bool
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    required_skill_ids: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = ()


class RequirementUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    normalized_requirement: str
    root_identity: str
    responsibilities: tuple[InterpretedResponsibility, ...] = Field(min_length=1)
    rationale: tuple[str, ...] = Field(min_length=1)


class CapabilityNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_id: str = Field(pattern=r"^node_[a-f0-9]{16}$")
    capability_identity: str = Field(min_length=3, max_length=128)
    parent_node_id: str | None = Field(default=None, pattern=r"^node_[a-f0-9]{16}$")
    depth: int = Field(ge=0)
    responsibility: str = Field(min_length=1)
    atomic: bool
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()
    required_capability_ids: tuple[str, ...] = ()
    required_skill_ids: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    permission_refs: tuple[str, ...] = ()
    scope_refs: tuple[str, ...] = Field(min_length=1)


class CapabilityGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    root_node_id: str = Field(pattern=r"^node_[a-f0-9]{16}$")
    nodes: tuple[CapabilityNode, ...] = Field(min_length=1)
    max_depth: int = Field(default=2, ge=0, le=8)


class CapabilityGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_id: str
    capability_identity: str
    reason: str


class CapabilityProfile(BaseModel):
    """Structured metadata supplementing the canonical Backend catalog projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    catalog_item: CapabilityCatalogItem
    input_semantics: tuple[str, ...] = ()
    output_semantics: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()


class RegistryDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dependency_id: str = Field(min_length=3, max_length=128)
    kind: Literal[DependencyKind.SKILL, DependencyKind.TOOL, DependencyKind.MODEL_POLICY]
    availability: Literal["AVAILABLE", "UNAVAILABLE"] = "AVAILABLE"
    configuration_status: Literal["CONFIGURED", "NEEDS_CONFIGURATION"] = "CONFIGURED"


class WorkforceRegistrySnapshot(BaseModel):
    """Read-only snapshot supplied by the authoritative Backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_profiles: tuple[CapabilityProfile, ...] = ()
    dependencies: tuple[RegistryDependency, ...] = ()


class CapabilityMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_id: str
    decision: Literal["REUSE", "CREATE"]
    matched_capability: CapabilityCatalogItem | None = None
    score: int = Field(ge=0)
    rationale: tuple[str, ...] = Field(min_length=1)


class DependencyRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dependency_id: str
    kind: DependencyKind
    status: DependencyStatus
    required: bool = True
    source: Literal["REQUIREMENT", "REGISTRY", "AUTHORITY_CONTEXT", "FACTORY"]
    detail: str = Field(min_length=1)


class EvaluationRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evaluation_id: str = Field(pattern=r"^eval_[a-f0-9]{16}$")
    kind: EvaluationKind
    objective: str = Field(min_length=1)
    expected_evidence: tuple[str, ...] = Field(min_length=1)


class PlannedAgent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    planned_agent_id: str = Field(pattern=r"^planned_agent_[a-f0-9]{16}$")
    node_id: str
    parent_agent_id: str | None = None
    responsibility: str
    capability_decision: Literal["REUSE", "CREATE"]
    capability_ref: str
    dependency_requirements: tuple[DependencyRequirement, ...]
    model_policy_ref: str | None = None
    budget_policy: ExecutionBudget | None = None
    delegation_policy: DelegationPolicyRequirement
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    evaluation_requirements: tuple[EvaluationRequirement, ...] = Field(min_length=1)
    readiness: Literal["READY_FOR_DRAFT", "READY_FOR_REUSE", "NEEDS_CONFIGURATION"]
    factory_result: FactoryAnalysisResult | None = None
    lifecycle_state: Literal["DRAFT"] = "DRAFT"


class AssuranceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: AssuranceCode
    node_id: str | None = None
    detail: str = Field(min_length=1)


class WorkforcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_id: str = Field(pattern=r"^workforce_plan_[a-f0-9]{16}$")
    requirement_understanding: RequirementUnderstanding
    capability_graph: CapabilityGraph
    capability_gaps: tuple[CapabilityGap, ...]
    planned_agents: tuple[PlannedAgent, ...] = Field(min_length=1)
    assurance_findings: tuple[AssuranceFinding, ...] = ()
    lifecycle_state: Literal["DRAFT"] = "DRAFT"
    human_gate_required: Literal[True] = True
    authoritative_state_changed: Literal[False] = False

    def canonical_agent_drafts(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            agent.factory_result.agent_draft.model_dump(mode="json")
            for agent in self.planned_agents
            if agent.factory_result is not None and agent.factory_result.agent_draft is not None
        )


class WorkforceAssuranceError(ValueError):
    def __init__(self, findings: tuple[AssuranceFinding, ...]) -> None:
        super().__init__("Workforce plan failed assurance")
        self.findings = findings

