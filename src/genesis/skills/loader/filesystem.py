from pathlib import Path

import yaml

from genesis.skills.loader.models import LoadedSkill, SkillDescriptor, SkillSpecification


class FileSystemSkillLoader:
    """Discovers metadata first and reads SKILL.md only when explicitly loaded."""

    def discover(self, root: Path) -> tuple[SkillDescriptor, ...]:
        descriptors: list[SkillDescriptor] = []
        for manifest_path in sorted(root.glob("**/skill.yaml")):
            document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            specification = SkillSpecification.model_validate(document)
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
            raise FileNotFoundError(f"Missing SKILL.md for {descriptor.specification.identity}")
        return LoadedSkill(
            specification=descriptor.specification,
            instructions=instructions_path.read_text(encoding="utf-8").strip(),
        )
