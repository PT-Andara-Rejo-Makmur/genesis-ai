# GENESIS Memory Intelligence (MVP2 H4 AI)

## Status and boundary

Memory is historical, governed context; it is never an authority source. The
Backend-issued `ExecutionContext` remains the maximum authority for tenant,
organization, workspace, scope, classification, permissions, roles, and tools.

GENESIS does not own a memory database, vector store, retention lifecycle, audit
log, or persistence endpoint. Canonical contracts version 1.5.0 does not yet define
`MemoryRecord`, `MemoryQuery`, or `MemoryWrite`. H4 AI therefore uses immutable
internal runtime projections and a framework-neutral `MemoryRetrievalPort`. A real
adapter is pending H4 Contracts/Backend work; no route or tool ID is invented here.

## Ownership

Backend owns authoritative persistence and isolation, retention/expiry/deletion,
classification and audit, source/evidence persistence, retrieval authorization,
future vector retrieval, and acceptance of write proposals.

GENESIS owns fail-closed candidate revalidation, deterministic relevance and
duplicate suppression, bounded ContextManager selection, write proposal decisions,
and shared R&D historical-memory semantics.

## Retrieval flow

The port returns Backend-governed candidates. `MemoryRetrievalService` then applies:

1. exact tenant, organization, and workspace checks;
2. scope subset of current and active scope;
3. classification ordering (`PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED`);
4. active status, expiry, and `CURRENT` freshness;
5. valid evidence/source lineage and identity/scope/classification checks;
6. requested R&D finding-kind and domain restrictions;
7. deterministic content/domain/kind duplicate fingerprinting;
8. explainable lexical, domain, explicit-ref, source, evidence, and recency scoring;
9. threshold and bounded maximum selection.

Boundary fields never add points. Unauthorized candidates are excluded before
deduplication or scoring. Input order does not affect the result, and structured
metadata records every duplicate suppression.

## ContextManager and historical lineage

`MemoryContextFactory` creates `RELEVANT_MEMORY` segments with a `memory_ref`; it
never injects text directly into a model prompt. The existing context budget can
drop memory before required security, authority, goal, and evidence segments.

The runtime bundle correlation always belongs to the current run. Historical origin
`run_id` and `correlation_id` remain unchanged in `EvidenceReference`. The safety
guard permits that difference only for memory; non-memory evidence still requires
the current correlation.

`ContextSource.MEMORY` is the runtime delivery source, while evidence retains its
canonical `INTERNAL` or `EXTERNAL` source type. External-origin memory remains
untrusted, has no instruction authority, and is checked for instruction injection.
Invalid, stale, cross-scope, cross-identity, or over-classified evidence cannot
become trusted merely because it was stored as memory.

## Write policy

`MemoryWritePolicy` has no persistence dependency. It returns only:

- `PROPOSE` for reusable, evidence-backed `VALIDATED`, `VERIFIED`, or `APPROVED` output;
- `REVIEW_REQUIRED` for otherwise eligible `AI_INFERRED`, `NEEDS_REVIEW`, or `DRAFT`;
- `REJECT` for forbidden states, missing lineage, authority expansion, transient
  content, unknown states, or detected credential material.

A proposal preserves identity, scope, classification, evidence, and origin. It
never self-approves, changes retention, writes storage, or obliges Backend to accept.

## R&D domains

One generic selector handles `TECHNOLOGY`, `PROPERTY_BUSINESS`, `MANAGEMENT`, and
`PROPERTY_MARKET`. `ResearchMemoryPolicy` supplies only domain configuration and
relevance hints. Domain-restricted research requires `FindingKind.RESEARCH`;
operational findings are not silently mixed into research history.

## No autonomous learning

The `learning` and `consolidation` packages do not train models, rewrite prompts,
modify Skills or AgentDefinitions, change policy, or mutate memory. Learning means
a governed proposal; consolidation means deterministic duplicate handling. The
memory core has no SQL, pgvector, vector client, provider SDK, arbitrary HTTP, or
Backend repository import.

## Backend/Contracts handoff

A future governed transport needs canonical definitions for candidate identity;
content and scope; classification; created/expiry timestamps; status and freshness;
source and full evidence lineage (hash, anchor, version, origin run/correlation);
optional research domain/finding kind; bounded query/pagination; and write proposal
submission plus Backend review/audit result.

Until those semantics exist in canonical contracts and Backend authority, real
Backend memory retrieval remains pending.
