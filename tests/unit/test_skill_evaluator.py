from pathlib import Path

from genesis.contracts import CanonicalContractCatalog
from genesis.skills.evaluator import EvaluationOutcome, SkillEvaluator
from genesis.skills.loader import SkillDefinition, SkillDescriptor, SkillReference
from genesis.skills.selection import (
    SkillCandidateOutcome,
    SkillSelectionStatus,
)

CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "alos-contracts"
SKILL_SCHEMA = "https://schemas.alos.dev/v1/skill/skill-definition.schema.json"


def specification() -> SkillDefinition:
    return SkillDefinition(
        skill_id="skill.test.evaluation",
        skill_version="1.0.0",
        name="Evaluation fixture",
        description="Reusable deterministic evaluator fixture.",
        purpose="Evaluate evidence-bound output.",
        when_to_use=("Evidence-bound output needs evaluation.",),
        input_schema_ref=SKILL_SCHEMA,
        output_schema_ref=SKILL_SCHEMA,
        procedure=("Evaluate output.",),
        required_tool_ids=("source.search_context",),
        evidence_requirements=("Cite every claim.",),
        restrictions=("Do not execute actions.",),
        failure_modes=("Insufficient evidence.",),
        escalation=("Request evidence.",),
        evaluation=("Every claim is cited.",),
    )


def evaluator() -> SkillEvaluator:
    return SkillEvaluator(contracts=CanonicalContractCatalog(CONTRACTS_ROOT))


def outcome(status: SkillSelectionStatus) -> SkillCandidateOutcome:
    definition = specification()
    descriptor = SkillDescriptor(specification=definition, package_path=Path("fixture"))
    return SkillCandidateOutcome(
        reference=SkillReference(skill_id=definition.skill_id, skill_version="1.0.0"),
        status=status,
        relevance_score=1,
        reason="Fixture outcome.",
        missing_tool_ids=(
            ("source.search_context",)
            if status is not SkillSelectionStatus.SELECTED
            else ()
        ),
        descriptor=descriptor,
    )


def test_applicability_reports_structured_pass_and_fail_reasons() -> None:
    applicable = evaluator().evaluate_applicability(
        outcome(SkillSelectionStatus.SELECTED), execution_context_present=True
    )
    blocked = evaluator().evaluate_applicability(
        outcome(SkillSelectionStatus.REQUIRED_TOOL_UNAVAILABLE),
        execution_context_present=False,
    )

    assert applicable.passed is True
    assert blocked.passed is False
    assert all(item.check_id and item.reason for item in blocked.checks)
    assert any(item.outcome is EvaluationOutcome.FAIL for item in blocked.checks)


def test_result_passes_contract_evidence_and_tool_checks() -> None:
    definition = specification()
    result = evaluator().evaluate_result(
        definition,
        output=definition.model_dump(mode="json"),
        evidence_refs=("evidence_001",),
        supplied_evidence_ids=("evidence_001",),
        used_tool_ids=("source.search_context",),
        authorized_tool_ids=("source.search_context",),
    )

    assert result.passed is True
    assert result.declared_criteria == ("Every claim is cited.",)


def test_invalid_output_unknown_evidence_and_tool_usage_are_rejected() -> None:
    result = evaluator().evaluate_result(
        specification(),
        output={"unexpected": True},
        evidence_refs=("evidence_unknown",),
        supplied_evidence_ids=("evidence_authorized",),
        used_tool_ids=("business.database.write",),
        authorized_tool_ids=("source.search_context",),
        limitations=("Evidence and output validation failed.",),
    )

    assert result.passed is False
    failed_ids = {
        item.check_id for item in result.checks if item.outcome is EvaluationOutcome.FAIL
    }
    assert failed_ids == {
        "skill.output_contract",
        "skill.evidence_refs_authorized",
        "skill.tool_usage_authorized",
    }


def test_insufficient_evidence_requires_explicit_limitation() -> None:
    result = evaluator().evaluate_result(
        specification(),
        output=specification().model_dump(mode="json"),
        evidence_refs=(),
        supplied_evidence_ids=(),
        used_tool_ids=(),
        authorized_tool_ids=(),
    )

    assert result.passed is False
    assert any(
        item.check_id == "skill.failure_or_limitations_explicit"
        and item.outcome is EvaluationOutcome.FAIL
        for item in result.checks
    )
