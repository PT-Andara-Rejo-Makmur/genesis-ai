from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillSpecification(BaseModel):
    """ALOS Skill Specification metadata; full instructions remain in SKILL.md."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: str = Field(min_length=3, max_length=128)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
    purpose: str = Field(min_length=1)
    when_to_use: tuple[str, ...] = Field(min_length=1)
    input: dict[str, Any]
    output: dict[str, Any]
    procedure: str = Field(min_length=1, description="Ringkasan; langkah penuh ada di SKILL.md")
    allowed_tools: tuple[str, ...] = ()
    evidence_requirement: tuple[str, ...] = ()
    restrictions: tuple[str, ...] = Field(min_length=1)
    failure_modes: tuple[str, ...] = Field(min_length=1)
    escalation: tuple[str, ...] = Field(min_length=1)
    evaluation: tuple[str, ...] = Field(min_length=1)


class SkillDescriptor(BaseModel):
    """Discovery result that deliberately omits full procedural instructions."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    specification: SkillSpecification
    package_path: Path


class LoadedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    specification: SkillSpecification
    instructions: str = Field(min_length=1)


class SkillDraft(BaseModel):
    """Self-created knowledge remains a draft until ALOS authority activates it."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    draft_id: str
    specification: SkillSpecification
    instructions: str = Field(min_length=1)
    created_by_run_id: str
    status: Literal["DRAFT", "SUBMITTED_FOR_REVIEW"] = "DRAFT"
