from genesis.orchestration.delegation.models import (
    DelegationPolicy,
    DelegationRequest,
    ParentRunState,
)


class DelegationDenied(Exception):
    pass


class DelegationGuard:
    """Prevents authority expansion, cycles, and unbounded child execution."""

    def validate(
        self,
        parent: ParentRunState,
        child: DelegationRequest,
        policy: DelegationPolicy,
    ) -> None:
        if child.root_run_id != parent.root_run_id or child.parent_run_id != parent.run_id:
            raise DelegationDenied("Delegation lineage does not match the parent run")
        if child.depth != parent.depth + 1 or child.depth > policy.max_depth:
            raise DelegationDenied("Delegation exceeds max_depth or has invalid depth")
        if parent.child_count >= policy.max_children:
            raise DelegationDenied("Delegation exceeds max_children")
        if child.child_agent_id in child.ancestry_agent_ids:
            raise DelegationDenied("Delegation cycle detected")
        if child.timeout_seconds > policy.timeout_seconds:
            raise DelegationDenied("Child timeout exceeds delegation policy")
        if child.authority.tenant_id != parent.authority.tenant_id:
            raise DelegationDenied("Child tenant cannot differ from parent")
        if child.authority.workspace_id != parent.authority.workspace_id:
            raise DelegationDenied("Child workspace cannot differ from parent")
        if not child.authority.permission_refs.issubset(parent.authority.permission_refs):
            raise DelegationDenied("Child permissions cannot exceed parent permissions")
        if not child.authority.scope_refs.issubset(parent.authority.scope_refs):
            raise DelegationDenied("Child scopes cannot exceed parent scopes")
        if not child.authority.allowed_tool_ids.issubset(parent.authority.allowed_tool_ids):
            raise DelegationDenied("Child tools cannot exceed parent tool restrictions")
        if not parent.budget.contains(child.budget):
            raise DelegationDenied("Child execution budget cannot exceed parent budget")
