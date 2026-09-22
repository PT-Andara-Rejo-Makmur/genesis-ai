# MVP2 H7 AI Handoff

## Delivered in GENESIS

- One generic `ResearchOrchestrator` for all four R&D domains.
- Strict, bounded ModelGateway question planning and claim extraction.
- Governed evidence-gap and tool-selection reuse from H5.
- H4 memory and completed/validated H6 child evidence ingestion.
- Deterministic evidence quality, provenance, freshness, scope, classification,
  and external-trust checks.
- Duplicate, independent corroboration, source-version, freshness, and claim
  conflict analysis.
- Candidate findings/recommendations with conservative confidence caps and
  mandatory human review.
- Exact validation against the existing canonical `ResearchResult` contract.

## Backend integration contract for H9

Backend remains authoritative for the run, permissions, scopes, tools, budgets,
source access, persistence, audit, approvals, and backlog. A later integration
must provide a `ResearchEvidenceProvider` adapter whose tool descriptors and
results are already bound to the authoritative run context. GENESIS defense in
depth never turns that port into independent authority.

The adapter must preserve:

- exact tenant/organization/workspace/scope and correlation identity;
- exact authorized tool identity and category;
- source/evidence identity, version, content hash, anchor, capture/retrieval time;
- classification, freshness, reliability, validation, and trust metadata;
- external content as `UNTRUSTED` with `instruction_authority=false`;
- explicit FAILED, TIMEOUT, DENIED, and NO_RESULT outcomes;
- no implicit retry, version substitution, or fabricated evidence.

Backend later owns durable source registration, research/audit records, approval
state, recommendation release, and any backlog conversion. Those operations are
not implemented in GENESIS H7.

## Canonicalization status

Contracts remain read-only at version 1.5.0. H7 planning, quality, claims,
conflicts, and recommendation analysis are internal projections. Only the
existing canonical `ResearchRequest`, context/evidence contracts, and
`ResearchResult` cross the public boundary. If H9 needs public H7 projections,
they require an explicit additive Contracts change rather than leaking internal
models.

## Acceptance boundary

H7 is suitable as the AI foundation for H8 governance only after local quality
and GitHub development quality pass. H8 must consume candidate recommendations
and review flags; it must not reinterpret them as approval or release authority.
