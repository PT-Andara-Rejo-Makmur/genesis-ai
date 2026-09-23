# MVP2 H8 AI Handoff

## AI consumes

- An exact, caller-supplied `ReviewSubjectSnapshot`, including subject ID/version,
  tenant/organization/workspace, correlation, capability draft, declared authority,
  policy projections, and execution budget.
- Canonical `EvidenceRef` objects from ALOS Contracts 1.5.0.
- Typed observations produced from H1-H7 component outputs and deterministic fixtures.
- An optional H7 `ResearchOrchestrationResult` for the shared R&D safety evaluation.

GENESIS never resolves a mutable "latest" registry object while evaluating a subject.

## AI produces

- `EvaluationSuiteResult` with PASS/FAIL/NOT_RUN, evidence, exact subject version, and correlation.
- The versioned `mvp2-h8-rc1-ai-regression` proposal.
- A deterministic `AIReadinessAssessment`.
- An operational `RiskEvidenceSummary` with all blockers visible and no private reasoning.
- Five canonically validated `AIReviewResult` projections.
- A canonically validated advisory `ReviewPackage` draft without human decisions.

`READY_FOR_IT_REVIEW` is not approval, release, or activation.

## Backend later owns

- Eval result/evidence persistence and authoritative audit correlation.
- Governance state and allowed transitions.
- IT and Director `DecisionRef` creation and separation-of-duties enforcement.
- Release, activation, suspension, rollback, and kill operations.
- R&D backlog review, prioritization, approval, and production backlog mutation.

## H9 integration gaps

- Canonical transport/persistence for internal eval artifacts if cross-service transport is required.
- The exact Backend endpoint for ReviewPackage submission.
- Backend mapping from advisory AI readiness to governance-command eligibility.
- Persistence of exact eval version/evidence and authoritative cost/audit correlation.
- Cross-repository RC1 and Gate 4 execution.

These are integration and authority boundaries, not deferred H8 AI features. No Backend or
Contracts behavior is implemented in GENESIS.
