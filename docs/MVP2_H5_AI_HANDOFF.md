# MVP2 H5 AI Handoff

This document records the boundary for independent AI and Backend development
through H8. Integration is deferred to H9 where canonical contracts remain absent.

## Consumes

- canonical `AgentRunRequest`;
- internal projection of the authoritative `AgentDefinition`;
- Backend-issued `RuntimeAuthorization`;
- canonical `ExecutionContext` and optional `ContextBundle`;
- canonical `ToolResult`;
- canonical `EvidenceRef` objects already admitted to ContextBundle.

## Produces

- canonical `ToolRequest` sent through `ToolBoundaryClient`;
- canonical `AgentRunResult`;
- internal, non-authoritative operational stop reason;
- internal research tool-selection decision and category.

The internal state and trace are deliberately excluded from AgentRunResult.

## Ports expected from Backend later

- `ToolBoundaryClient` connected to the authoritative ToolExecutor path;
- `CancellationProbe`/run-control source;
- authoritative run and step persistence;
- governed external-research tool implementation and registration;
- canonical model/tool cost persistence and accounting record;
- canonical audit sink.

## GENESIS does not own

- ToolExecutor or business adapters;
- run/step persistence;
- cancellation authority or state mutation;
- external-provider credentials or direct provider access;
- approval, release, or lifecycle transition;
- backlog persistence;
- authoritative tool registration or retention.

## Contract gaps for H9 integration

Contracts version 1.5.0 does not currently define:

- `RuntimeStep` or persisted trajectory representation;
- cancellation command/state boundary;
- approval-request event/representation;
- detailed multi-step usage and per-step cost;
- generic research tool-category descriptor metadata.

H5 AI uses frozen internal models and ports for these concerns. No canonical schema,
status, API, event, or tool registration was added in another repository.

## Operational integration notes

- Tool identity must remain the intersection of request intent, AgentDefinition,
  and Backend authorization.
- Backend ToolResult must echo run, tool-call, tool, and correlation identifiers.
- Planner-side ModelGateway usage must be reported to the runtime so cumulative
  tokens and known cost remain visible.
- ToolResult has no canonical generic cost field; GENESIS does not invent one.
- Generic ToolResult output cannot become EvidenceRef without a validated
  tool-specific projection in a future governed contract.
- Historical memory evidence keeps its original run/correlation lineage while the
  current AgentRunResult keeps the current run correlation.
