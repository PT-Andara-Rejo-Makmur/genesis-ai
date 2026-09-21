from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillDefinition(BaseModel):
    """Immutable typed projection of canonical ALOS SkillDefinition 1.4.0."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    skill_id: str = Field(min_length=3, max_length=128)
    skill_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    )
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    purpose: str = ""
    when_to_use: tuple[str, ...] = ()
    input_schema_ref: str
    output_schema_ref: str
    procedure: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    restrictions: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    escalation: tuple[str, ...] = ()
    evaluation: tuple[str, ...] = ()


class SkillReference(BaseModel):
    """Backend-authorized skill identity/version pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    skill_id: str = Field(min_length=3, max_length=128)
    skill_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    )


class SkillDescriptor(BaseModel):
    """Discovery result that deliberately omits full procedural instructions."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    specification: SkillDefinition
    package_path: Path

    @property
    def reference(self) -> SkillReference:
        return SkillReference(
            skill_id=self.specification.skill_id,
            skill_version=self.specification.skill_version,
        )


class LoadedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    specification: SkillDefinition
    instructions: str = Field(min_length=1)
    package_path: Path


class SkillDraft(BaseModel):
    """Self-created knowledge remains a draft until ALOS authority activates it."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    draft_id: str
    specification: SkillDefinition
    instructions: str = Field(min_length=1)
    created_by_run_id: str
    status: Literal["DRAFT", "SUBMITTED_FOR_REVIEW"] = "DRAFT"


class SkillFailureCode(StrEnum):
    INVALID_MANIFEST = "INVALID_MANIFEST"
    MISSING_PACKAGE = "MISSING_PACKAGE"
    MISSING_INSTRUCTIONS = "MISSING_INSTRUCTIONS"
    UNAUTHORIZED = "UNAUTHORIZED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    NO_RELEVANT_SKILL = "NO_RELEVANT_SKILL"
    REQUIRED_TOOL_UNAVAILABLE = "REQUIRED_TOOL_UNAVAILABLE"
    LOAD_LIMIT_EXCEEDED = "LOAD_LIMIT_EXCEEDED"


class SkillPackageError(Exception):
    """Structured, non-sensitive, fail-closed package/runtime failure."""

    def __init__(
        self,
        code: SkillFailureCode,
        message: str,
        *,
        skill_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.skill_id = skill_id

    def as_dict(self) -> dict[str, str | bool]:
        result: dict[str, str | bool] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": False,
        }
        if self.skill_id is not None:
            result["skill_id"] = self.skill_id
        return result
