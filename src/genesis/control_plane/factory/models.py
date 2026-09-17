from pydantic import BaseModel, ConfigDict, Field

from genesis.capabilities import CapabilityDefinition


class CapabilityFactoryProposal(BaseModel):
    """A proposal only; ALOS Backend owns registry activation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str = Field(min_length=3)
    requirement: str = Field(min_length=1)
    capability: CapabilityDefinition
    rationale: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
