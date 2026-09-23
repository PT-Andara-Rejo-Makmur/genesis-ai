# Pre-H9 Codebase Hygiene

## Baseline and scope

This cleanup started from `cf3c8789dfc6d9c1b6daf57d9cd96be521870c56` on
`development`. It is limited to permanent naming, type ownership, obsolete compatibility
removal, package structure, assurance organization, tests, and current architecture docs.
It adds no H9 feature and changes no authority or intelligence policy.

## Naming policy

Permanent production identifiers describe product semantics, not delivery milestones.
Research policies use `policy.research.*`; assurance cases use `assurance.*`; the core
regression proposal is `CORE_AI_ASSURANCE_REGRESSION_SET`; and research model limits use
`DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET`. Historical handoff and release evidence retains its
original milestone vocabulary.

## Canonical and internal type policy

- `AgentDefinition` is a typed runtime projection using canonical field vocabulary such as
  `skill_refs`, `tool_ids`, `permission_refs`, `scope_refs`, `model_policy_ref`, and
  `delegation_policy`. Canonical JSON Schema validation remains at application boundaries.
- `AgentDraftProposal` is the single Factory/governance draft projection. It remains
  non-authoritative and is validated against the Contracts draft schema.
- `FactoryExecutionContext` and factory `AuthorityContext` remain separate from runtime
  `ExecutionContextView` and runtime `AuthorityContext`: the former projects a canonical
  Factory request, while the latter represents narrowed runtime execution facts.
- `ToolBoundaryContracts` remains a focused facade because the Backend tool boundary has an
  independent schema set and fail-closed validation responsibility.

## Removals

- The duplicate internal `AgentDraft`, obsolete `WorkforceControlPlane`, and its assessment
  scaffold.
- Unused `AgentRunInput`, `AgentRunResult`, and `AgentRuntime` protocol scaffolding together
  with the unused PydanticAI wrapper that depended on it.
- The one-shot `ExecutionPlan`, `RuntimePlanner`, `SinglePassPlanner`, and mixed core-runtime
  compatibility branch.
- The unused `FindingRecommendationBuilder.build()` compatibility helper.
- Empty package trees that represented unimplemented lifecycle, supervision, remediation,
  sustainability, evaluation taxonomy folders, memory learning/consolidation, planning,
  synthesis, research domain placeholders, review disciplines, and runtime recovery.

## Renames

- `AgentDraft` (Factory projection) to `AgentDraftProposal`.
- Skill `EvaluationOutcome` to `SkillEvaluationOutcome`.
- `H7_DEFAULT_MODEL_TOKEN_BUDGET` to `DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET`.
- `MVP2_H8_REGRESSION_SET` to `CORE_AI_ASSURANCE_REGRESSION_SET`.
- Regression ID `mvp2-h8-rc1-ai-regression` to `core-ai-assurance-regression`.
- Regression provenance field `created_from_milestone` to `provenance_label`, with value
  `core-ai-feature-freeze`.
- Research policy and assurance case identifiers to permanent semantic namespaces.

## Preserved compatibility and intentional projections

No milestone-named source compatibility aliases remain. The regression proposal version stays
`1.0.0` because the predicates, ordering, severity, and behavior are unchanged; only its
permanent identity vocabulary changed. `CapabilityDefinition`, `AgentBlueprint`, review
models/protocols, and evaluation planning models remain because they are active, tested,
domain-specific abstractions rather than duplicate canonical models.

`ResearchEngine` remains the canonical request/result application facade.
`ResearchOrchestrator` remains the internal evidence/claims/conflict/findings/recommendation
pipeline. `BackendToolClient` remains the correct HTTP path to the authoritative Backend.

## Assurance and package structure

Assurance probes are separated into context, skill, memory, runtime, delegation, and research
modules with a small deterministic registry and export module. An AST-backed hygiene test
prevents milestone identifiers, duplicate Agent draft definitions, and one-shot planner types
from returning to permanent source.

## H9 handoff notes

H9 may integrate additional canonical fields or adapters only through existing validated
boundaries. Any contract mismatch discovered then belongs in a separate Contracts change; this
cleanup does not alter `alos-contracts`, Backend, frontend, infrastructure, release state, or
approval authority.

## Behavior-preservation proof

The cleanup retains all deterministic predicates, budgets, case ordering, evidence and
authority subset checks, canonical validation, safe-failure behavior, and Backend/ModelGateway
boundaries. Proof is the unchanged behavioral regression suite plus Ruff, mypy, full pytest,
startup import smoke, and the GitHub `quality` workflow on `development`.
