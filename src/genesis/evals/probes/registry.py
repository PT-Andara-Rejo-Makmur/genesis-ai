"""Deterministic registration of assurance probes in catalog order."""

from genesis.evals.models import (
    ContextObservation,
    DelegationObservation,
    MemoryObservation,
    ObservationProof,
    ResearchObservation,
    RuntimeObservation,
    SkillObservation,
)
from genesis.evals.probes.base import ProbeEvaluator, RegisteredInvariantProbe
from genesis.evals.probes.context import context_evaluator
from genesis.evals.probes.delegation import delegation_evaluator
from genesis.evals.probes.memory import memory_evaluator
from genesis.evals.probes.research import research_evaluator as make_research_evaluator
from genesis.evals.probes.runtime import runtime_evaluator
from genesis.evals.probes.skill import skill_evaluator
from genesis.evals.regression import RegressionSetProposal
from genesis.evals.research import RDSafetyEvaluator


def registered_probes(
    proposal: RegressionSetProposal,
    *,
    research_evaluator: RDSafetyEvaluator | None,
) -> tuple[RegisteredInvariantProbe, ...]:
    probes: list[RegisteredInvariantProbe] = []
    for case in proposal.case_refs:
        evaluator: ProbeEvaluator
        observation_type: type[ObservationProof]
        if case.area.value == "CONTEXT":
            evaluator, observation_type = context_evaluator(case.eval_case_id), ContextObservation
        elif case.area.value == "SKILL":
            evaluator, observation_type = skill_evaluator(case.eval_case_id), SkillObservation
        elif case.area.value == "MEMORY":
            evaluator, observation_type = memory_evaluator(case.eval_case_id), MemoryObservation
        elif case.area.value == "RUNTIME":
            evaluator, observation_type = runtime_evaluator(case.eval_case_id), RuntimeObservation
        elif case.area.value == "DELEGATION":
            evaluator, observation_type = (
                delegation_evaluator(case.eval_case_id),
                DelegationObservation,
            )
        elif research_evaluator is not None:
            evaluator = make_research_evaluator(case.eval_case_id, research_evaluator)
            observation_type = ResearchObservation
        else:
            continue
        probes.append(RegisteredInvariantProbe(case.eval_case_id, evaluator, observation_type))
    return tuple(probes)
