"""Research assurance probe predicates."""

from typing import cast

from genesis.evals.models import EvaluationObservation, ResearchObservation
from genesis.evals.probes.base import ProbeEvaluator
from genesis.evals.research import RDSafetyEvaluator


def research_evaluator(case_id: str, evaluator: RDSafetyEvaluator) -> ProbeEvaluator:
    mapping = {
        "assurance.research.citation-lineage": (
            "rd.canonical-lineage",
            "rd.citation-complete",
            "rd.fact-evidence",
            "rd.finding-evidence",
            "rd.recommendation-links",
        ),
        "assurance.research.external-trust": ("rd.external-trust", "rd.external-evidence"),
        "assurance.research.freshness-conflict": ("rd.freshness", "rd.conflicts"),
        "assurance.research.assumption-fact": ("rd.assumptions",),
        "assurance.research.safe-failure": ("rd.safe-failure",),
        "assurance.research.domain-quality": (
            "rd.source-quality",
            "rd.recommendation-quality",
            "rd.domain-quality",
            "rd.advisory-only",
        ),
    }

    def evaluate(raw: EvaluationObservation) -> tuple[bool, str, tuple[str, ...]]:
        item = cast(ResearchObservation, raw)
        assessment = evaluator.evaluate(item.result)
        by_id = {check.check_id: check for check in assessment.checks}
        required = mapping[case_id]
        missing = tuple(check_id for check_id in required if check_id not in by_id)
        failed = tuple(
            check_id for check_id in required if check_id in by_id and not by_id[check_id].passed
        )
        passed = not missing and not failed
        reasons = tuple(
            dict.fromkeys(reason for check_id in failed for reason in by_id[check_id].reason_codes)
        )
        if missing:
            reasons = (*reasons, "R_AND_D_SAFETY_CHECK_MISSING")
        if passed:
            reasons = ("R_AND_D_SAFETY_CHECKS_PASSED",)
        return passed, "R&D invariant derived from the shared RDSafetyEvaluator.", reasons

    return evaluate
