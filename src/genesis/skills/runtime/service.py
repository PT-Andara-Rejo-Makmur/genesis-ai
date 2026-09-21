from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from genesis.skills.loader import FileSystemSkillLoader, LoadedSkill, SkillReference
from genesis.skills.progressive_loading import ProgressiveSkillLoader
from genesis.skills.selection import SkillSelection, SkillSelector


class SkillRuntimeStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class SkillRuntimeContext(BaseModel):
    """Procedural context only; it carries no authority and performs no action."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: SkillRuntimeStatus
    selection: SkillSelection
    loaded_skills: tuple[LoadedSkill, ...]


class SkillRuntime:
    """Generic metadata selection and progressive-loading coordinator."""

    def __init__(
        self,
        *,
        loader: FileSystemSkillLoader,
        selector: SkillSelector | None = None,
        maximum_loaded: int = 4,
    ) -> None:
        self._loader = loader
        self._selector = selector or SkillSelector()
        self._progressive = ProgressiveSkillLoader(loader, maximum_loaded=maximum_loaded)

    def prepare(
        self,
        packages_root: Path,
        *,
        authorized_refs: Sequence[SkillReference],
        goal: str,
        backend_allowed_tool_ids: Sequence[str],
        agent_allowed_tool_ids: Sequence[str] | None = None,
        capability_context: Sequence[str] = (),
        maximum_selected: int = 1,
    ) -> SkillRuntimeContext:
        descriptors = self._loader.discover(packages_root)
        selection = self._selector.select(
            descriptors,
            authorized_refs=authorized_refs,
            goal=goal,
            backend_allowed_tool_ids=backend_allowed_tool_ids,
            agent_allowed_tool_ids=agent_allowed_tool_ids,
            capability_context=capability_context,
            maximum_selected=maximum_selected,
        )
        loaded = self._progressive.load_selected(selection.selected)
        return SkillRuntimeContext(
            status=SkillRuntimeStatus.READY if loaded else SkillRuntimeStatus.BLOCKED,
            selection=selection,
            loaded_skills=loaded,
        )
