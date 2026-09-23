from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class MaterialBehaviorObservation(BaseModel):
    """Typed fixture/output adapter consumed by registered invariant probes."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    passed: bool
    observed: str = Field(min_length=1)
    reason_codes: tuple[str, ...] = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()
    evidence_refs: tuple[dict[str, Any], ...] = ()
    fixture_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


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
    observations: dict[str, MaterialBehaviorObservation] = Field(default_factory=dict)


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
