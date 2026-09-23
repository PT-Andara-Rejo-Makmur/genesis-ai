from collections.abc import Sequence

from genesis.skills.loader import (
    FileSystemSkillLoader,
    LoadedSkill,
    SkillFailureCode,
    SkillPackageError,
)
from genesis.skills.selection import SkillCandidateOutcome, SkillSelectionStatus


class ProgressiveSkillLoader:
    """Load instructions only for the bounded outcomes selected by SkillSelector."""

    def __init__(self, loader: FileSystemSkillLoader, *, maximum_loaded: int = 4) -> None:
        if maximum_loaded < 1:
            raise ValueError("maximum_loaded must be at least one")
        self._loader = loader
        self._maximum_loaded = maximum_loaded

    def load_selected(self, selected: Sequence[SkillCandidateOutcome]) -> tuple[LoadedSkill, ...]:
        if len(selected) > self._maximum_loaded:
            raise SkillPackageError(
                SkillFailureCode.LOAD_LIMIT_EXCEEDED,
                "Selected skill count exceeds the progressive loading bound.",
            )
        loaded: list[LoadedSkill] = []
        for outcome in selected:
            if outcome.status is not SkillSelectionStatus.SELECTED or outcome.descriptor is None:
                raise SkillPackageError(
                    SkillFailureCode.UNAUTHORIZED,
                    "Only explicitly selected skill descriptors may load instructions.",
                    skill_id=outcome.reference.skill_id,
                )
            loaded.append(self._loader.load(outcome.descriptor))
        return tuple(loaded)
