"""Deterministic structural synthesis of validated child observations."""

import json
from collections.abc import Sequence

from genesis.orchestration.delegation.models import (
    ChildObservation,
    DelegationDisposition,
    DelegationSynthesis,
)


class DelegationSynthesizer:
    def synthesize(self, observations: Sequence[ChildObservation]) -> DelegationSynthesis:
        successful = tuple(
            item
            for item in observations
            if item.validation_status == "VALID" and item.status == "COMPLETED"
        )
        failed = tuple(item for item in observations if item not in successful)
        if successful and not failed:
            disposition = DelegationDisposition.COMPLETE
            reasons = ("ALL_CHILDREN_COMPLETED",)
        elif successful:
            disposition = DelegationDisposition.PARTIAL
            reasons = ("SOME_CHILDREN_FAILED_OR_INVALID",)
        elif any(item.validation_status == "INVALID" for item in failed):
            disposition = DelegationDisposition.NEEDS_REVIEW
            reasons = ("CHILD_RESULT_INVALID",)
        else:
            disposition = DelegationDisposition.FAILED
            reasons = ("NO_CHILD_COMPLETED",)
        evidence_by_lineage: dict[str, dict[str, object]] = {}
        for item in successful:
            for evidence in item.evidence_refs:
                identity = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
                evidence_by_lineage[identity] = evidence
        return DelegationSynthesis(
            disposition=disposition,
            successful_children=successful,
            failed_children=failed,
            evidence_refs=tuple(
                evidence_by_lineage[key] for key in sorted(evidence_by_lineage)
            ),
            reason_codes=reasons,
        )
