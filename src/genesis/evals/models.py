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
