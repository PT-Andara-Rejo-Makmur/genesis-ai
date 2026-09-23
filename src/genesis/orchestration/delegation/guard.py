"""Defense-in-depth delegation checks; Backend remains authoritative."""

from genesis.orchestration.delegation.models import (
    DelegationAuthorizationSnapshot,
    DelegationIntent,
)
from genesis.orchestration.delegation.planner import expected_delegation_key
from genesis.runtime.context import DataClassification

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class DelegationDenied(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DelegationGuard:
    """Reject expansion, cycles, duplicate submission, and unbounded allocation."""

    def validate(
        self,
        snapshot: DelegationAuthorizationSnapshot,
        intent: DelegationIntent,
        *,
        submitted_keys: frozenset[str] = frozenset(),
        reserved_tokens: int = 0,
        reserved_cost: float = 0,
        child_count: int = 0,
    ) -> None:
        if not snapshot.enabled:
            raise DelegationDenied("DELEGATION_DISABLED", "Delegation is disabled")
        if (
            intent.root_run_id != snapshot.root_run_id
            or intent.parent_run_id != snapshot.parent_run_id
        ):
            raise DelegationDenied("DELEGATION_LINEAGE_MISMATCH", "Parent lineage mismatch")
        if (
            intent.parent_agent_id != snapshot.parent_agent_id
            or intent.parent_agent_version != snapshot.parent_agent_version
        ):
            raise DelegationDenied("DELEGATION_PARENT_MISMATCH", "Parent Agent mismatch")
        if intent.depth != snapshot.parent_depth + 1 or intent.depth > snapshot.max_depth:
            raise DelegationDenied("DELEGATION_DEPTH_EXCEEDED", "Invalid delegation depth")
        if child_count >= snapshot.max_children:
            raise DelegationDenied("DELEGATION_CHILD_LIMIT", "Maximum children reached")
        if intent.delegation_key in submitted_keys:
            raise DelegationDenied("DUPLICATE_DELEGATION", "Delegation already submitted")
        if intent.delegation_key != expected_delegation_key(intent):
            raise DelegationDenied("DELEGATION_KEY_INVALID", "Delegation identity is invalid")
        expected_ancestry = (
            *snapshot.ancestry_agent_refs,
            f"{snapshot.parent_agent_id}@{snapshot.parent_agent_version}",
        )
        if intent.ancestry_agent_refs != expected_ancestry:
            raise DelegationDenied("DELEGATION_ANCESTRY_MISMATCH", "Ancestry is invalid")

        target = next(
            (
                item
                for item in snapshot.allowed_child_targets
                if item.agent_id == intent.target_agent_id
                and item.agent_version == intent.target_agent_version
            ),
            None,
        )
        if target is None:
            raise DelegationDenied("CHILD_TARGET_DENIED", "Exact child target is not allowed")
        if intent.target_capability_id not in target.capability_ids:
            raise DelegationDenied("CHILD_CAPABILITY_DENIED", "Child capability is not allowed")
        target_ref = target.exact_ref
        parent_ref = f"{snapshot.parent_agent_id}@{snapshot.parent_agent_version}"
        if target_ref == parent_ref or target_ref in snapshot.ancestry_agent_refs:
            raise DelegationDenied("DELEGATION_CYCLE", "Delegation cycle detected")

        child = intent.requested_authority.authority
        parent = snapshot.effective_parent_authority
        if child.tenant_id != parent.tenant_id:
            raise DelegationDenied("CHILD_TENANT_MISMATCH", "Child tenant differs")
        if child.organization_id != parent.organization_id:
            raise DelegationDenied("CHILD_ORGANIZATION_MISMATCH", "Child organization differs")
        if child.workspace_id != parent.workspace_id:
            raise DelegationDenied("CHILD_WORKSPACE_MISMATCH", "Child workspace differs")
        if not child.permission_refs.issubset(parent.permission_refs):
            raise DelegationDenied("CHILD_PERMISSION_EXPANSION", "Permissions expand")
        if not child.scope_refs.issubset(parent.scope_refs):
            raise DelegationDenied("CHILD_SCOPE_EXPANSION", "Scopes expand")
        if not child.allowed_tool_ids.issubset(parent.allowed_tool_ids):
            raise DelegationDenied("CHILD_TOOL_EXPANSION", "Tools expand")
        if (
            _CLASSIFICATION_RANK[child.data_classification]
            > _CLASSIFICATION_RANK[parent.data_classification]
        ):
            raise DelegationDenied("CHILD_CLASSIFICATION_EXPANSION", "Classification expands")

        budget = intent.requested_authority.budget
        if not snapshot.parent_budget.contains(budget):
            raise DelegationDenied("CHILD_BUDGET_EXPANSION", "Child budget expands")
        if (
            snapshot.parent_budget.max_tokens is not None
            and budget.max_tokens is not None
            and reserved_tokens + budget.max_tokens > snapshot.parent_budget.max_tokens
        ):
            raise DelegationDenied("CHILD_TOKEN_RESERVATION_EXCEEDED", "Token reserve exceeded")
        if (
            snapshot.parent_budget.max_cost is not None
            and budget.max_cost is not None
            and reserved_cost + budget.max_cost > snapshot.parent_budget.max_cost
        ):
            raise DelegationDenied("CHILD_COST_RESERVATION_EXCEEDED", "Cost reserve exceeded")
        self._validate_research(snapshot, intent)

    @staticmethod
    def _validate_research(
        snapshot: DelegationAuthorizationSnapshot, intent: DelegationIntent
    ) -> None:
        child = intent.requested_authority.research_constraints
        parent = snapshot.research_constraints
        if child is None:
            if intent.task.domain is not None:
                raise DelegationDenied(
                    "RESEARCH_CONSTRAINTS_REQUIRED", "Domain task requires research constraints"
                )
            return
        if parent is None:
            raise DelegationDenied("RESEARCH_CONSTRAINT_EXPANSION", "Research not authorized")
        if not child.allowed_domains.issubset(parent.allowed_domains):
            raise DelegationDenied("RESEARCH_DOMAIN_EXPANSION", "Research domain expands")
        if not child.allowed_source_categories.issubset(parent.allowed_source_categories):
            raise DelegationDenied("RESEARCH_SOURCE_EXPANSION", "Source category expands")
        if child.external_research_allowed and not parent.external_research_allowed:
            raise DelegationDenied("RESEARCH_EGRESS_EXPANSION", "External egress expands")
        if child.maximum_external_cost > parent.maximum_external_cost:
            raise DelegationDenied("RESEARCH_COST_EXPANSION", "External cost expands")
        if (
            _CLASSIFICATION_RANK[child.data_classification_ceiling]
            > _CLASSIFICATION_RANK[parent.data_classification_ceiling]
        ):
            raise DelegationDenied("RESEARCH_CLASSIFICATION_EXPANSION", "Research class expands")
        if (
            _CLASSIFICATION_RANK[child.data_classification_ceiling]
            > _CLASSIFICATION_RANK[intent.requested_authority.authority.data_classification]
        ):
            raise DelegationDenied(
                "RESEARCH_CLASSIFICATION_EXPANSION", "Research exceeds child classification"
            )
        if intent.task.domain is not None and intent.task.domain not in child.allowed_domains:
            raise DelegationDenied("RESEARCH_DOMAIN_DENIED", "Task domain is not authorized")
