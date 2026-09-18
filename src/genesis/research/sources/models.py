"""Typed source semantics for evidence supplied to GENESIS research."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(StrEnum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


class SourceReliability(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FreshnessStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ContentTrust(StrEnum):
    GOVERNED = "GOVERNED"
    UNTRUSTED = "UNTRUSTED"


class SourceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str = Field(min_length=3, max_length=128)
    origin: str = Field(min_length=1)
    retrieved_at: datetime
    source_version: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ResearchSourceMetadata(BaseModel):
    """Evidence metadata; source content never receives instruction authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source_type: SourceType
    provenance: SourceProvenance
    freshness: FreshnessStatus
    reliability: SourceReliability
    content_trust: ContentTrust
    evidence_ref: str = Field(min_length=3, max_length=128)
    instruction_authority: Literal[False] = False

    @model_validator(mode="after")
    def external_content_is_untrusted(self) -> "ResearchSourceMetadata":
        if (
            self.source_type is SourceType.EXTERNAL
            and self.content_trust is not ContentTrust.UNTRUSTED
        ):
            raise ValueError("EXTERNAL source content must be marked UNTRUSTED")
        return self


class ResearchSourceMaterial(BaseModel):
    """Source text carried as evidence data, never as a GENESIS instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    metadata: ResearchSourceMetadata
    content_role: Literal["EVIDENCE_DATA"] = "EVIDENCE_DATA"
    content: str = Field(min_length=1, max_length=200_000)
    executable_instructions: Literal[False] = False
