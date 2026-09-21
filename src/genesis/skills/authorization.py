"""Immutable Backend-issued authorization snapshot for skill filtering."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from genesis.runtime.context.models import ExecutionContextView
from genesis.skills.loader.models import SkillReference


class SkillAuthorizationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    organization_id: str
    workspace_id: str
    correlation_id: str
    authorized_skill_refs: tuple[SkillReference, ...]
    permission_refs: tuple[str, ...]
    scope_refs: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]

    @classmethod
    def from_backend(
        cls,
        context: ExecutionContextView,
        *,
        authorized_skill_refs: Sequence[SkillReference],
        agent_skill_refs: Sequence[SkillReference] | None = None,
    ) -> SkillAuthorizationSnapshot:
        authorized = {(item.skill_id, item.skill_version): item for item in authorized_skill_refs}
        if agent_skill_refs is not None:
            agent = {(item.skill_id, item.skill_version) for item in agent_skill_refs}
            authorized = {key: value for key, value in authorized.items() if key in agent}
        return cls(
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            correlation_id=context.correlation_id,
            authorized_skill_refs=tuple(authorized[key] for key in sorted(authorized)),
            permission_refs=tuple(sorted(set(context.permission_refs))),
            scope_refs=tuple(sorted(set(context.scope_refs))),
            allowed_tool_ids=tuple(sorted(set(context.allowed_tool_ids))),
        )
