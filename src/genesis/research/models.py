from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FindingKind(StrEnum):
    RESEARCH = "RESEARCH"
    OPERATIONAL = "OPERATIONAL"


class ResearchDomain(StrEnum):
    TECHNOLOGY = "TECHNOLOGY"
    PROPERTY_BUSINESS = "PROPERTY_BUSINESS"
    MANAGEMENT = "MANAGEMENT"
    PROPERTY_MARKET = "PROPERTY_MARKET"


class ResearchFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    finding_id: str = Field(min_length=3)
    kind: FindingKind
    domain: ResearchDomain
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recommendation_id: str = Field(min_length=3)
    finding_ids: tuple[str, ...] = Field(min_length=1)
    proposed_action: str = Field(min_length=1)
    requires_human_review: bool = True


class BacklogCandidate(BaseModel):
    """Candidate only; creating it never executes the recommendation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str = Field(min_length=3)
    recommendation_id: str = Field(min_length=3)
    title: str = Field(min_length=1)
    status: str = "PROPOSED"
