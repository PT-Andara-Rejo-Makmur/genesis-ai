# MVP2 H6 AI Handoff

H6 delegation models in GENESIS are internal, immutable planning projections. They are not
canonical contracts and do not grant child authority.

## AI consumes

- Backend-issued parent execution authorization and canonical `AgentRunRequest`.
- An exact authorized-child-target snapshot supplied through the internal H6 handoff.
- The effective parent authority, execution budget, depth, ancestry, and research constraints.
- Canonical child `AgentRunResult` payloads returned by `DelegationBoundaryClient`.

## AI produces

- An internal `DelegationIntent` containing an exact target and deterministic delegation key.
- A structured `ChildTaskSpec` and narrower requested authority/budget.
- A validated `ChildObservation`; malformed results are explicitly marked invalid.
- A deterministic `DelegationSynthesis` with successful and failed children separated.

## Backend later owns

- Authoritative child-run creation and exact child Agent lifecycle validation.
- Persistent parent/child/root lineage and server-side inheritance enforcement.
- Persistent concurrency/depth accounting, cancellation propagation, retry, audit, and cost.
- The actual child `AgentRunRequest`; GENESIS never mints authoritative child run IDs.
- An authoritative delegation snapshot (or equivalent server-side session) bound to the current
  parent run, root, Agent/version, identity, effective authority, and ExecutionBudget.
- True server-side child count, active concurrency, depth, and tree-wide budget accounting.

GENESIS validates the supplied snapshot against the current parent request and runtime authority
before exposing delegation, but these checks remain defense in depth. Backend must bind the
snapshot/session server-side and repeat all authority and capacity decisions at child creation.

## Contract gaps for H9

- Canonical DelegationIntent/child-task request.
- Exact authorized-child-target snapshot.
- Ancestry/depth and delegation-idempotency projections.
- Research source/egress inheritance.
- Multi-child/tree usage accounting.
- Cancellation propagation representation.
- Canonical snapshot/session binding and exact target input/output schema metadata.

Until H9 closes these gaps, the Backend adapter remains a port only. GENESIS performs local
fail-closed preflight but does not claim that preflight is authoritative.
