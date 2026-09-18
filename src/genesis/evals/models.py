from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvaluationTaxonomy(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    REGRESSION = "REGRESSION"
    SECURITY = "SECURITY"
    RECOVERY = "RECOVERY"


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
