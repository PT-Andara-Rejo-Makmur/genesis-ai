import pytest

from genesis.orchestration.delegation import (
    AuthorityEnvelope,
    DelegationDenied,
    DelegationGuard,
    DelegationPolicy,
    DelegationRequest,
    ParentRunState,
)
from genesis.runtime.limits import ExecutionBudget


def parent() -> ParentRunState:
    return ParentRunState(
        run_id="run_parent_001",
        root_run_id="run_root_001",
        agent_id="agent_parent",
        depth=1,
        child_count=0,
        authority=AuthorityEnvelope(
            tenant_id="tenant_001",
            workspace_id="workspace_001",
            permission_refs=frozenset({"research.read"}),
            scope_refs=frozenset({"scope.research"}),
            allowed_tool_ids=frozenset({"tool.source.read"}),
        ),
        budget=ExecutionBudget(
            max_tokens=1000,
            max_children=2,
            max_depth=3,
            timeout_seconds=60,
        ),
    )


def child(**overrides: object) -> DelegationRequest:
    values: dict[str, object] = {
        "run_id": "run_child_001",
        "root_run_id": "run_root_001",
        "parent_run_id": "run_parent_001",
        "child_agent_id": "agent_child",
        "depth": 2,
        "ancestry_agent_ids": ("agent_parent",),
        "authority": parent().authority,
        "budget": ExecutionBudget(
            max_tokens=500,
            max_children=1,
            max_depth=2,
            timeout_seconds=30,
        ),
        "timeout_seconds": 30,
        "task": {"question": "Summarize evidence"},
    }
    values.update(overrides)
    return DelegationRequest.model_validate(values)


def policy() -> DelegationPolicy:
    return DelegationPolicy(max_depth=3, max_children=2, timeout_seconds=60)


def test_child_delegation_cannot_exceed_max_depth() -> None:
    with pytest.raises(DelegationDenied, match="max_depth"):
        DelegationGuard().validate(parent(), child(depth=4), policy())


def test_child_authority_cannot_expand() -> None:
    expanded = parent().authority.model_copy(
        update={"permission_refs": frozenset({"research.read", "business.write"})}
    )
    with pytest.raises(DelegationDenied, match="permissions"):
        DelegationGuard().validate(parent(), child(authority=expanded), policy())


def test_valid_child_inherits_bounded_authority_and_budget() -> None:
    DelegationGuard().validate(parent(), child(), policy())
