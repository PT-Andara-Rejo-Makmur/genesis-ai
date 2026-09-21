from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.skills.loader.models import (
    LoadedSkill,
    SkillDataFile,
    SkillDefinition,
    SkillDescriptor,
    SkillFailureCode,
    SkillPackageError,
)

SKILL_DEFINITION_SCHEMA = "https://schemas.alos.dev/v1/skill/skill-definition.schema.json"
ALLOWED_DATA_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".json"})


class FileSystemSkillLoader:
    """Discover canonical metadata, then explicitly load selected procedural data."""

    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def discover(self, root: Path) -> tuple[SkillDescriptor, ...]:
        if not root.is_dir():
            raise SkillPackageError(
                SkillFailureCode.MISSING_PACKAGE,
                "Skill package root is unavailable.",
            )
        descriptors: list[SkillDescriptor] = []
        references: set[tuple[str, str]] = set()
        for manifest_path in sorted(root.glob("**/skill.yaml")):
            try:
                document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(document, Mapping):
                    raise ValueError("manifest must be a mapping")
                canonical = self._contracts.validate(
                    SKILL_DEFINITION_SCHEMA,
                    cast(Mapping[str, Any], document),
                )
                canonical.pop("tool_ids", None)
                specification = SkillDefinition.model_validate(canonical)
            except (
                OSError,
                ValueError,
                ValidationError,
                ContractValidationError,
                yaml.YAMLError,
            ) as exc:
                raise SkillPackageError(
                    SkillFailureCode.INVALID_MANIFEST,
                    f"Invalid canonical skill manifest: {manifest_path.name}.",
                ) from exc
            reference = (specification.skill_id, specification.skill_version)
            if reference in references:
                raise SkillPackageError(
                    SkillFailureCode.INVALID_MANIFEST,
                    "Duplicate skill identity and version discovered.",
                    skill_id=specification.skill_id,
                )
            references.add(reference)
            descriptors.append(
                SkillDescriptor(
                    specification=specification,
                    package_path=manifest_path.parent,
                )
            )
        return tuple(descriptors)

    def load(self, descriptor: SkillDescriptor) -> LoadedSkill:
        instructions_path = descriptor.package_path / "SKILL.md"
        if not instructions_path.is_file():
            raise SkillPackageError(
                SkillFailureCode.MISSING_INSTRUCTIONS,
                "Selected skill package is missing SKILL.md.",
                skill_id=descriptor.specification.skill_id,
            )
        instructions = instructions_path.read_text(encoding="utf-8").strip()
        if not instructions:
            raise SkillPackageError(
                SkillFailureCode.MISSING_INSTRUCTIONS,
                "Selected skill package has an empty SKILL.md.",
                skill_id=descriptor.specification.skill_id,
            )
        data_files = []
        for path in sorted(descriptor.package_path.rglob("*")):
            if not path.is_file() or path.name in {"skill.yaml", "SKILL.md"}:
                continue
            if path.suffix.lower() not in ALLOWED_DATA_SUFFIXES:
                raise SkillPackageError(
                    SkillFailureCode.INVALID_MANIFEST,
                    "Skill package contains a forbidden executable or binary file.",
                    skill_id=descriptor.specification.skill_id,
                )
            data_files.append(
                SkillDataFile(
                    relative_path=path.relative_to(descriptor.package_path).as_posix(),
                    content=path.read_text(encoding="utf-8"),
                )
            )
        return LoadedSkill(
            specification=descriptor.specification,
            instructions=instructions,
            package_path=descriptor.package_path,
            data_files=tuple(data_files),
        )
