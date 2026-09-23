"""Skill assurance probe predicates."""

from typing import cast

from genesis.evals.models import EvaluationObservation, SkillObservation
from genesis.evals.probes.base import ProbeEvaluator
from genesis.skills.evaluator import SkillEvaluationOutcome


def skill_evaluator(case_id: str) -> ProbeEvaluator:
    def evaluate(raw: EvaluationObservation) -> tuple[bool, str, tuple[str, ...]]:
        item = cast(SkillObservation, raw)
        checks = {check.check_id: check.outcome for check in item.evaluation.checks}
        if case_id == "assurance.skill.exact-result":
            passed = (
                item.expected_skill_version == item.observed_skill_version
                and item.evaluation.passed
                and not item.authority_expanded
            )
        else:
            check_id = {
                "assurance.skill.unknown-evidence": "skill.evidence_refs_authorized",
                "assurance.skill.unauthorized-tool": "skill.tool_usage_authorized",
                "assurance.skill.missing-required-tool": "skill.required_tools_authorized",
            }[case_id]
            passed = (
                checks.get(check_id) is SkillEvaluationOutcome.FAIL and not item.authority_expanded
            )
        return (
            passed,
            "Skill invariant derived from the existing SkillEvaluator checks.",
            (("SKILL_EVALUATOR_ENFORCED",) if passed else ("SKILL_EVALUATOR_REGRESSION",)),
        )

    return evaluate
