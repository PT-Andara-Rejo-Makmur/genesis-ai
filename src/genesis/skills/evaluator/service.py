from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from genesis.contracts import CanonicalContractCatalog, ContractValidationError
from genesis.skills.loader import SkillDefinition
from genesis.skills.selection import SkillCandidateOutcome, SkillSelectionStatus


class SkillEvaluationOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - evaluation outcome, not a credential
    FAIL = "FAIL"


class EvaluationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check_id: str
    outcome: SkillEvaluationOutcome
    reason: str = Field(min_length=1)


class SkillEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    passed: bool
    checks: tuple[EvaluationCheck, ...]
    declared_criteria: tuple[str, ...]


class SkillEvaluator:
    """Deterministic platform checks; declared English criteria remain declarative."""

    def __init__(self, *, contracts: CanonicalContractCatalog) -> None:
        self._contracts = contracts

    def evaluate_applicability(
        self,
        outcome: SkillCandidateOutcome,
        *,
        execution_context_present: bool,
        context_prerequisites_satisfied: bool = True,
    ) -> SkillEvaluation:
        selected = outcome.status is SkillSelectionStatus.SELECTED
        checks = (
            self._check("skill.authorized_and_relevant", selected, outcome.reason),
            self._check(
                "skill.required_tools_authorized",
                selected or not outcome.missing_tool_ids,
                (
                    "Required tools are within the effective allowlist."
                    if not outcome.missing_tool_ids
                    else "Missing required tools: " + ", ".join(outcome.missing_tool_ids) + "."
                ),
            ),
            self._check(
                "skill.execution_context_present",
                execution_context_present,
                "A validated Backend-issued execution context is required.",
            ),
            self._check(
                "skill.context_prerequisites",
                context_prerequisites_satisfied,
                "Required narrowed context prerequisites must be present.",
            ),
        )
        criteria = outcome.descriptor.specification.evaluation if outcome.descriptor else ()
        return SkillEvaluation(
            passed=all(item.outcome is SkillEvaluationOutcome.PASS for item in checks),
            checks=checks,
            declared_criteria=criteria,
        )

    def evaluate_result(
        self,
        specification: SkillDefinition,
        *,
        output: Mapping[str, Any],
        evidence_refs: Sequence[Mapping[str, Any] | str],
        supplied_evidence_ids: Sequence[str],
        used_tool_ids: Sequence[str],
        authorized_tool_ids: Sequence[str],
        limitations: Sequence[str] = (),
    ) -> SkillEvaluation:
        checks: list[EvaluationCheck] = []
        try:
            self._contracts.validate(specification.output_schema_ref, output)
        except (ContractValidationError, ValueError) as exc:
            checks.append(
                self._check("skill.output_contract", False, f"Output contract failed: {exc}")
            )
        else:
            checks.append(
                self._check("skill.output_contract", True, "Output satisfies its canonical schema.")
            )

        cited = {
            item if isinstance(item, str) else str(item.get("evidence_id", ""))
            for item in evidence_refs
        }
        cited.discard("")
        supplied = set(supplied_evidence_ids)
        evidence_present = not specification.evidence_requirements or bool(cited)
        checks.append(
            self._check(
                "skill.required_evidence_present",
                evidence_present,
                (
                    "Required evidence references are present."
                    if evidence_present
                    else "The result omits evidence required by the skill."
                ),
            )
        )
        unknown = sorted(cited - supplied)
        checks.append(
            self._check(
                "skill.evidence_refs_authorized",
                not unknown,
                (
                    "All cited evidence came from the supplied authorized evidence set."
                    if not unknown
                    else "Unknown evidence references: " + ", ".join(unknown) + "."
                ),
            )
        )
        unsupported_tools = sorted(set(used_tool_ids) - set(authorized_tool_ids))
        checks.append(
            self._check(
                "skill.tool_usage_authorized",
                not unsupported_tools,
                (
                    "All reported tool usage is within the effective allowlist."
                    if not unsupported_tools
                    else "Unsupported tool usage: " + ", ".join(unsupported_tools) + "."
                ),
            )
        )
        requirements_met = evidence_present and not unknown and not unsupported_tools
        checks.append(
            self._check(
                "skill.failure_or_limitations_explicit",
                requirements_met or bool(limitations),
                (
                    "No unmet platform requirement requires a limitation."
                    if requirements_met
                    else "Unmet requirements must produce an explicit limitation or failure state."
                ),
            )
        )
        return SkillEvaluation(
            passed=all(item.outcome is SkillEvaluationOutcome.PASS for item in checks),
            checks=tuple(checks),
            declared_criteria=specification.evaluation,
        )

    @staticmethod
    def _check(check_id: str, passed: bool, reason: str) -> EvaluationCheck:
        return EvaluationCheck(
            check_id=check_id,
            outcome=SkillEvaluationOutcome.PASS if passed else SkillEvaluationOutcome.FAIL,
            reason=reason,
        )
