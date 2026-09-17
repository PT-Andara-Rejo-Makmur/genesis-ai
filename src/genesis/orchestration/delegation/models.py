from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from genesis.runtime.limits import ExecutionBudget


class AuthorityEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=3)
    workspace_id: str = Field(min_length=3)
    permission_refs: frozenset[str] = frozenset()
    scope_refs: frozenset[str] = Field(min_length=1)
    allowed_tool_ids: frozenset[str] = frozenset()


class DelegationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_depth: int = Field(ge=0)
    max_children: int = Field(ge=0)
    timeout_seconds: int = Field(ge=1)


class ParentRunState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3)
    root_run_id: str = Field(min_length=3)
    agent_id: str = Field(min_length=3)
    depth: int = Field(ge=0)
    child_count: int = Field(ge=0)
    authority: AuthorityEnvelope
    budget: ExecutionBudget


class DelegationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=3)
    root_run_id: str = Field(min_length=3)
    parent_run_id: str = Field(min_length=3)
    child_agent_id: str = Field(min_length=3)
    depth: int = Field(ge=1)
    ancestry_agent_ids: tuple[str, ...]
    authority: AuthorityEnvelope
    budget: ExecutionBudget
    timeout_seconds: int = Field(ge=1)
    task: dict[str, Any]


class ChildRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    parent_run_id: str
    root_run_id: str
    status: Literal["COMPLETED", "FAILED", "DENIED", "TIMED_OUT"]
    output: Any = None
    evidence_refs: tuple[str, ...] = ()
