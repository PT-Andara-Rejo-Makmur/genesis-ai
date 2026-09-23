from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from genesis.research.orchestration import ResearchOrchestrationResult
from genesis.skills.evaluator import SkillEvaluation


class EvaluationTaxonomy(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    REGRESSION = "REGRESSION"
    SECURITY = "SECURITY"
    RECOVERY = "RECOVERY"


class EvaluationArea(StrEnum):
    CONTEXT = "CONTEXT"
    SKILL = "SKILL"
    MEMORY = "MEMORY"
    RUNTIME = "RUNTIME"
    DELEGATION = "DELEGATION"
    RESEARCH = "RESEARCH"


class EvaluationOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - an assurance outcome, not a credential
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class EvaluationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    MATERIAL = "MATERIAL"
    BLOCKER = "BLOCKER"


class EvaluationEvidence(BaseModel):
    """Safe observable facts. This deliberately has no reasoning/scratchpad field."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_ids: tuple[str, ...] = ()
    evidence_refs: tuple[dict[str, Any], ...] = ()
    fixture_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = Field(min_length=1)
    observations: tuple[str, ...] = ()


class EvaluationAssertionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    assertion_id: str = Field(min_length=3, max_length=128)
    passed: bool
    expected: str = Field(min_length=1)
    observed: str = Field(min_length=1)


class ObservationProof(BaseModel):
    """Observable artifacts only; reason codes alone never prove a material PASS."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_ids: tuple[str, ...] = ()
    evidence_refs: tuple[dict[str, Any], ...] = ()
    fixture_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class ContextObservation(ObservationProof):
    kind: Literal["CONTEXT"] = "CONTEXT"
    expected_tenant_id: str
    expected_organization_id: str | None = None
    expected_workspace_id: str
    expected_scope_refs: tuple[str, ...]
    expected_classification: str
    observed_tenant_id: str
    observed_organization_id: str | None = None
    observed_workspace_id: str
    observed_scope_refs: tuple[str, ...]
    observed_classification: str
    evidence_valid: bool = False
    source_type: str | None = None
    content_trust: str | None = None
    instruction_authority: bool = False
    rejected: bool = False
    rejection_code: str | None = None


class SkillObservation(ObservationProof):
    kind: Literal["SKILL"] = "SKILL"
    expected_skill_version: str
    observed_skill_version: str
    evaluation: SkillEvaluation
    authority_expanded: bool = False


class MemoryObservation(ObservationProof):
    kind: Literal["MEMORY"] = "MEMORY"
    identity_matches: bool
    scope_subset: bool
    classification_allowed: bool
    relevant: bool
    selected: bool
    expired: bool = False
    stale: bool = False
    treated_as_current: bool = False
    duplicate_count: int = Field(default=0, ge=0)
    duplicate_limit: int = Field(default=1, ge=0)
    independent_lineage_expected: int = Field(default=0, ge=0)
    independent_lineage_retained: int = Field(default=0, ge=0)


class RuntimeObservation(ObservationProof):
    kind: Literal["RUNTIME"] = "RUNTIME"
    run_status: str
    stop_reason: str | None = None
    consumed_tokens: int = Field(ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    estimated_cost: float = Field(ge=0)
    max_cost: float | None = Field(default=None, ge=0)
    tool_failure_observed: bool = False
    fabricated_success: bool = False
    cancellation_requested: bool = False
    approval_required: bool = False
    unauthorized_tool_requested: bool = False
    unauthorized_boundary_call: bool = False
    model_call_after_exhaustion: bool = False
    evidence_trust_preserved: bool = True
    evidence_classification_preserved: bool = True


class DelegationObservation(ObservationProof):
    kind: Literal["DELEGATION"] = "DELEGATION"
    target_exact: bool
    child_permission_refs: tuple[str, ...]
    parent_permission_refs: tuple[str, ...]
    child_scope_refs: tuple[str, ...]
    parent_scope_refs: tuple[str, ...]
    child_tool_ids: tuple[str, ...]
    parent_tool_ids: tuple[str, ...]
    child_budget_tokens: int = Field(ge=0)
    parent_budget_tokens: int = Field(ge=0)
    parent_consumed_tokens: int = Field(ge=0)
    reserved_child_tokens: int = Field(ge=0)
    depth_violation: bool = False
    cycle_detected: bool = False
    duplicate_detected: bool = False
    invalid_attempt_rejected: bool = False
    continued_after_tree_budget_violation: bool = False
    child_result_canonical: bool = True
    child_instruction_authority: bool = False


class ResearchObservation(ObservationProof):
    kind: Literal["RESEARCH"] = "RESEARCH"
    result: ResearchOrchestrationResult


EvaluationObservation = Annotated[
    ContextObservation
    | SkillObservation
    | MemoryObservation
    | RuntimeObservation
    | DelegationObservation
    | ResearchObservation,
    Field(discriminator="kind"),
]


class EvaluationSubjectSnapshot(BaseModel):
    """Exact caller-supplied subject; GENESIS never resolves a mutable latest version."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_id: str = Field(min_length=3, max_length=128)
    subject_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    )
    tenant_id: str = Field(min_length=3, max_length=128)
    organization_id: str | None = Field(default=None, min_length=3, max_length=128)
    workspace_id: str = Field(min_length=3, max_length=128)
    correlation_id: str = Field(min_length=3, max_length=128)
    observations: dict[str, EvaluationObservation] = Field(default_factory=dict)


class EvaluationCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    test_id: str = Field(min_length=3, max_length=128)
    area: EvaluationArea
    taxonomy: EvaluationTaxonomy
    outcome: EvaluationOutcome
    severity: EvaluationSeverity
    required: bool
    summary: str = Field(min_length=1)
    assertions: tuple[EvaluationAssertionResult, ...] = Field(min_length=1)
    evidence: EvaluationEvidence
    limitations: tuple[str, ...] = ()
    correlation_id: str
    subject_id: str
    subject_version: str


class EvaluationSuiteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    suite_id: str = Field(min_length=3, max_length=128)
    suite_version: str
    subject_id: str
    subject_version: str
    tenant_id: str
    organization_id: str | None = None
    workspace_id: str
    correlation_id: str
    case_results: tuple[EvaluationCaseResult, ...] = Field(min_length=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    not_run: int = Field(ge=0)
    material_failure_ids: tuple[str, ...] = ()
    evidence_refs: tuple[dict[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_result_integrity(self) -> EvaluationSuiteResult:
        ids = [item.test_id for item in self.case_results]
        if len(ids) != len(set(ids)):
            raise ValueError("Evaluation suite case IDs must be unique")
        expected_counts = (
            sum(item.outcome is EvaluationOutcome.PASS for item in self.case_results),
            sum(item.outcome is EvaluationOutcome.FAIL for item in self.case_results),
            sum(item.outcome is EvaluationOutcome.NOT_RUN for item in self.case_results),
        )
        if expected_counts != (self.passed, self.failed, self.not_run):
            raise ValueError("Evaluation suite counts do not match case results")
        expected_material = tuple(
            item.test_id
            for item in self.case_results
            if item.outcome is EvaluationOutcome.FAIL
            and item.severity in {EvaluationSeverity.MATERIAL, EvaluationSeverity.BLOCKER}
        )
        if self.material_failure_ids != expected_material:
            raise ValueError("Evaluation suite material failures do not match case results")
        return self


class RiskBasedTestProfile(BaseModel):
    """Selects relevant taxonomies; not every capability requires every category."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profile_id: str = Field(min_length=3)
    capability_id: str = Field(min_length=3)
    risk_level: str
    required_taxonomies: frozenset[EvaluationTaxonomy] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class EvaluationCase(BaseModel):
    """Expected behavior must be evaluated; category never implies a pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    test_id: str = Field(min_length=3, max_length=128)
    taxonomy: EvaluationTaxonomy
    input_fixture: dict[str, object]
    expected_status: str = Field(min_length=1)
    expected_error_code: str | None = None
    assertions: tuple[str, ...] = Field(min_length=1)


class EvaluationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: RiskBasedTestProfile
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)
