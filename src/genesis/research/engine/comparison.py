"""Pure document comparison intelligence adapted from MVP-1."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ComparisonFindingKind(StrEnum):
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    MISSING_FIELD = "MISSING_FIELD"
    OUTDATED_REFERENCE = "OUTDATED_REFERENCE"


class ComparableDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str = Field(min_length=3)
    source_version: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    content: str = Field(min_length=1)


class ComparisonFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: ComparisonFindingKind
    source_ids: tuple[str, ...] = Field(min_length=1)
    statement: str
    requires_human_decision: bool = True


class DocumentComparisonIntelligence:
    """Detect obvious document risks without persistence or authoritative mutation."""

    def compare(
        self,
        documents: tuple[ComparableDocument, ...],
        *,
        required_fields: tuple[str, ...] = (),
        current_year: int,
    ) -> tuple[ComparisonFinding, ...]:
        findings: list[ComparisonFinding] = []
        hashes: dict[str, list[str]] = {}
        key_values: dict[str, dict[str, list[str]]] = {}
        for document in documents:
            hashes.setdefault(document.content_hash, []).append(document.source_id)
            parsed = self._key_values(document.content)
            for key, value in parsed.items():
                key_values.setdefault(key, {}).setdefault(value, []).append(document.source_id)
            lowered = document.content.casefold()
            for required in required_fields:
                if required.casefold() not in parsed:
                    findings.append(
                        ComparisonFinding(
                            kind=ComparisonFindingKind.MISSING_FIELD,
                            source_ids=(document.source_id,),
                            statement=f"Required field is missing: {required}",
                        )
                    )
            years = {int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", lowered)}
            if any(year < current_year for year in years):
                findings.append(
                    ComparisonFinding(
                        kind=ComparisonFindingKind.OUTDATED_REFERENCE,
                        source_ids=(document.source_id,),
                        statement="Document contains a reference older than the comparison year.",
                    )
                )
        for source_ids in hashes.values():
            if len(source_ids) > 1:
                findings.append(
                    ComparisonFinding(
                        kind=ComparisonFindingKind.DUPLICATE,
                        source_ids=tuple(sorted(source_ids)),
                        statement="Documents have identical immutable content hashes.",
                    )
                )
        for key, values in key_values.items():
            if len(values) > 1:
                source_ids = sorted({source for sources in values.values() for source in sources})
                findings.append(
                    ComparisonFinding(
                        kind=ComparisonFindingKind.CONFLICT,
                        source_ids=tuple(source_ids),
                        statement=f"Documents contain conflicting values for field: {key}",
                    )
                )
        return tuple(findings)

    @staticmethod
    def _key_values(content: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in content.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() and value.strip():
                values[key.strip().casefold()] = value.strip()
        return values
