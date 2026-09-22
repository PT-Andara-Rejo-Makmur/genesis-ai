# Bounded Agentic Runtime (MVP2 H5 AI)

## Purpose

`AgentRuntimeEngine` performs bounded planning, governed tool intent, observation,
and deterministic stopping. It is not an autonomous authority. Every run starts
from a canonical `AgentRunRequest`, a declarative `AgentDefinition`, and a
Backend-issued `RuntimeAuthorization` snapshot.

```text
goal/input
  -> next structured action
     -> TOOL -> canonical ToolRequest -> Backend ToolExecutor -> ToolResult
        -> validate and observe -> next action
     -> FINISH / NEEDS_INFO / APPROVAL_REQUIRED / FAIL
  -> canonical AgentRunResult
```

The engine stores only operational state: identifiers, counts, validated tool
observations, known evidence IDs, cumulative usage, and correlation. It does not
store private chain-of-thought.

## Actions and compatibility

The internal action types are `TOOL`, `FINISH`, `NEEDS_INFO`,
`APPROVAL_REQUIRED`, and `FAIL`. An `AgenticPlanner` emits one strict action at a
time and can inspect prior bounded observations. Existing `RuntimePlanner.plan()`
implementations remain supported through a compatibility path, and
`SinglePassPlanner` also implements the iterative interface.

Planner implementations that call a model must use `ModelGateway` and report
validated usage in `planner_usage`; there is no direct provider SDK in runtime
core. Final synthesis also goes through `ModelGateway` and receives only the
remaining token allowance.

## Bounds and stopping

Every iterative run requires `max_steps`, `max_tool_calls`, and `max_tokens`.
The engine additionally enforces `max_cost` when present and wraps the entire run
in `timeout_seconds` when present. Tokens and known model cost are cumulative,
not reset per step.

Internal stop reasons include success, needs information, approval required,
tool denied/failed, model failed, invalid output, insufficient evidence, exhausted
budget, timeout, cancellation, maximum steps, and maximum tool calls. These are
projected onto existing contract statuses only:

- success: `COMPLETED` + `AI_INFERRED`;
- needs information or approval: `COMPLETED` + `NEEDS_REVIEW` when the Agent
  output schema permits a structured review output;
- cancellation: `CANCELLED` plus canonical error;
- whole-run timeout: `TIMED_OUT` plus canonical error;
- other failures: `FAILED` with `BLOCKED` or `NEEDS_REVIEW`.

No new canonical status is invented. If a review output cannot satisfy the
Agent's output schema, the runtime fails safely instead of fabricating output.

## Tool and authority boundary

A tool executes only when its ID is present in all three sets:

```text
AgentRunRequest.requested_tool_ids
  INTERSECT AgentDefinition.allowed_tool_ids
  INTERSECT RuntimeAuthorization.allowed_tool_ids
```

The engine builds and validates a canonical ToolRequest, including a deterministic
tool-call ID and idempotency key derived from run ID, step, tool ID, and canonical
arguments. Backend remains authoritative and returns a canonical ToolResult. The
engine validates the result contract and verifies run, tool-call, tool, and
correlation identifiers before observation.

`DENIED`, `REJECTED`, `FAILED`, and `TIMEOUT` stop safely. H5 performs no blind
automatic retry, and arbitrary ToolResult output is data without instruction
authority. GENESIS contains no ToolExecutor or business adapter.

## Evidence policy

The runtime can select only canonical EvidenceRef objects already present in the
validated ContextBundle and admitted as current/valid/current-scope evidence.
Planners reference known evidence IDs; unknown IDs fail as
`EVIDENCE_INSUFFICIENT`. Generic ToolResult output is never interpreted as a new
EvidenceRef.

`ExternalResearchDecider` remains the single channel policy: current internal
evidence first, current authorized memory second when risk permits, then a Backend
retrieval proposal only if authority and cost permit. External content remains
untrusted and has no instruction authority.

## Cancellation and approval

`CancellationProbe` is a non-authoritative read port. The default never-cancelled
implementation is local; Backend will later supply the real run-control source.
The engine checks it before planning, tool execution, and final model synthesis.
GENESIS never persists cancellation.

When a structured decision requires approval, or `AgentDefinition.approval_required`
guards a material tool action, the engine stops before the tool. It neither grants
nor simulates approval.

## R&D tool selection

One `ResearchToolSelectionPolicy` supports Technology, Property Business,
Management, and Property Market. It reuses `ExternalResearchDecider` and selects
only caller-supplied descriptors that remain within tool, permission, scope, risk,
classification, domain, and cost bounds. Categories are internal AI semantics,
not Backend registrations.

## Scope exclusions

H5 does not implement delegation, child execution, run/step persistence, audit
persistence, an external provider, approval/release mutation, or Backend
cancellation. Those remain later integration responsibilities.
