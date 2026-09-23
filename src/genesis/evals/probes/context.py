"""Context assurance probe predicates."""

from typing import cast

from genesis.evals.models import ContextObservation, EvaluationObservation
from genesis.evals.probes.base import ProbeEvaluator

_CLASSIFICATION_RANK = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}


def context_evaluator(case_id: str) -> ProbeEvaluator:
    def evaluate(raw: EvaluationObservation) -> tuple[bool, str, tuple[str, ...]]:
        item = cast(ContextObservation, raw)
        identity_exact = (
            item.observed_tenant_id == item.expected_tenant_id
            and item.observed_organization_id == item.expected_organization_id
            and item.observed_workspace_id == item.expected_workspace_id
        )
        scope_subset = set(item.observed_scope_refs).issubset(item.expected_scope_refs)
        classification_allowed = _CLASSIFICATION_RANK.get(
            item.observed_classification, 99
        ) <= _CLASSIFICATION_RANK.get(item.expected_classification, -1)
        if case_id == "assurance.context.scoped-valid":
            passed = (
                identity_exact and scope_subset and classification_allowed and item.evidence_valid
            )
        elif case_id == "assurance.context.cross-tenant":
            passed = item.observed_tenant_id != item.expected_tenant_id and item.rejected
        elif case_id == "assurance.context.cross-workspace":
            passed = item.observed_workspace_id != item.expected_workspace_id and item.rejected
        elif case_id == "assurance.context.scope-expansion":
            passed = not scope_subset and item.rejected
        elif case_id == "assurance.context.classification-expansion":
            passed = not classification_allowed and item.rejected
        else:
            passed = (
                item.source_type == "EXTERNAL"
                and item.content_trust == "UNTRUSTED"
                and item.instruction_authority is False
                and item.evidence_valid
            )
        return (
            passed,
            "Context invariant derived from identity, scope, classification, and trust facts.",
            (("CONTEXT_INVARIANT_SATISFIED",) if passed else ("CONTEXT_INVARIANT_VIOLATED",)),
        )

    return evaluate
