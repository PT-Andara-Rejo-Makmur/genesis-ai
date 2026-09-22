# Delegation System

## Authority model

A parent may propose a child task only for an exact `agent_id`, `agent_version`, and capability
present in the Backend/caller-supplied target snapshot. The requested child envelope must keep
tenant, organization, and workspace identical while narrowing classification, permissions,
scopes, tools, research source/egress constraints, and every bounded budget field.

`DelegationGuard` is defense in depth. Backend remains the authority for registry lifecycle,
child-run creation, persistence, audit, and server-side inheritance.

## Runtime flow

The H5 loop accepts an internal `DELEGATE` action. It checks cancellation, validates the
deterministic intent locally, and calls the separate `DelegationBoundaryClient`. Delegation is
not represented as a ToolRequest and GENESIS never invokes `AgentRuntimeEngine` recursively.
The boundary returns a canonical `AgentRunResult`, including its authoritative child run ID.

The result is contract-validated and checked for root, parent, correlation, Agent version,
capability, output schema, and evidence safety. External evidence remains untrusted and all
evidence remains non-instructional. Invalid results become explicit invalid observations; they
do not silently enter parent output or evidence.

## Bounds and failure behavior

- Exact versioned ancestry detects direct and indirect cycles.
- Depth, child count, cumulative child token reservation, and cumulative child cost reservation
  are bounded before submission.
- A normalized deterministic key suppresses duplicate material delegation before a second call.
- Child FAILED, CANCELLED, and TIMED_OUT statuses remain structured observations.
- There is no automatic retry and no authoritative cancellation propagation in GENESIS.
- Child usage is retained on the child observation and is not folded into parent canonical usage.

## Synthesis and research domains

`DelegationSynthesizer` deterministically labels COMPLETE, PARTIAL, FAILED, or NEEDS_REVIEW,
preserves valid evidence lineage, and never invents missing facts. Child output is data, never
authority or instruction.

One `ResearchDomainDelegationPolicy` supports TECHNOLOGY, PROPERTY_BUSINESS, MANAGEMENT, and
PROPERTY_MARKET. It maps only explicit domain subtasks to exact authorized targets and preserves
the parent's source-category, external-egress, cost, and classification ceilings. H7 query
decomposition, comparison, conflict analysis, and recommendation intelligence are not present.

## H9 handoff

H9 should canonicalize the temporary handoff projections and connect the boundary to Backend
child-run authority. Backend must add persistence, audit, concurrency, cancellation propagation,
retry, and tree-wide accounting without moving those responsibilities into GENESIS.
