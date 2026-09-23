"""Memory assurance probe predicates."""

from typing import cast

from genesis.evals.models import EvaluationObservation, MemoryObservation
from genesis.evals.probes.base import ProbeEvaluator


def memory_evaluator(case_id: str) -> ProbeEvaluator:
    def evaluate(raw: EvaluationObservation) -> tuple[bool, str, tuple[str, ...]]:
        item = cast(MemoryObservation, raw)
        if case_id == "assurance.memory.scoped-current":
            passed = all(
                (
                    item.identity_matches,
                    item.scope_subset,
                    item.classification_allowed,
                    item.relevant,
                    item.selected,
                    not item.expired,
                    not item.stale,
                )
            )
        elif case_id == "assurance.memory.expired-or-stale":
            passed = (item.expired or item.stale) and not item.treated_as_current
        elif case_id == "assurance.memory.cross-scope":
            passed = (
                not item.identity_matches
                or not item.scope_subset
                or not item.classification_allowed
            ) and not item.selected
        else:
            passed = (
                item.duplicate_count <= item.duplicate_limit
                and item.independent_lineage_retained >= item.independent_lineage_expected
            )
        return (
            passed,
            "Memory invariant derived from selection, authority, freshness, and lineage facts.",
            (("MEMORY_INVARIANT_SATISFIED",) if passed else ("MEMORY_INVARIANT_VIOLATED",)),
        )

    return evaluate
