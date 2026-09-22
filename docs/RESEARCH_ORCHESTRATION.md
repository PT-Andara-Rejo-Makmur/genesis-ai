# Research Orchestration

H7 adds one generic research-intelligence pipeline for TECHNOLOGY,
PROPERTY_BUSINESS, MANAGEMENT, and PROPERTY_MARKET. It composes the existing
H4 memory input, H5 governed retrieval selection, H6 validated child evidence,
and the canonical `ResearchEngine` result boundary. It does not create a second
runtime, tool executor, or authority source.

## Processing flow

```text
canonical ResearchRequest
  -> bounded ResearchQuestionPlanner (ModelGateway)
  -> deterministic evidence-gap decision
  -> ResearchToolSelectionPolicy
  -> ResearchEvidenceProvider port
  -> deterministic EvidenceQualityPolicy
  -> bounded ResearchClaimExtractor (ModelGateway)
  -> duplicate/corroboration/conflict comparison
  -> FindingRecommendationBuilder
  -> canonical ResearchResult validation
```

The planner emits at most eight typed subqueries. The claim extractor receives
at most twelve evidence items and 12,000 content characters. Both model calls
use strict JSON projections, report usage, and receive only bounded operational
data. No hidden chain of thought is requested or persisted.

## Authority and retrieval

`ResearchEvidenceProvider` is a port. Its implementation is owned by the caller
and must already represent Backend-authorized retrieval. GENESIS selects only
from supplied `AuthorizedResearchTool` descriptors and reuses
`ExternalResearchDecider` plus `ResearchToolSelectionPolicy`.

Internal documents, public datasets, connectors, and memory remain preferred
when suitable. External research is a governed last escalation and must satisfy
permission, scope, tool, classification, risk, and external-cost checks. A
retrieval failure is recorded as a limitation and is never silently retried or
fabricated.

## Evidence safety and quality

Every item is checked deterministically for tenant, organization, workspace,
scope, classification, validation, provenance, freshness, reliability, and
instruction authority. External evidence must remain `UNTRUSTED` and
non-instructional. Completed and validated H6 child evidence may enter the
catalog; failed, timed-out, cancelled, or invalid child evidence does not.

Quality is monotonic: stronger reliability/freshness may increase usability,
while stale, weak, unverified, invalid, missing-lineage, cross-scope, or
over-classified evidence can only reduce or exclude it. Model output cannot
upgrade deterministic evidence quality.

## Claims, conflicts, findings, and recommendations

The model may propose typed facts, assumptions, and gaps, but evidence IDs must
already exist. Lineage is derived from governed evidence rather than accepted
from model output. Same content and lineage is a duplicate; independent sources
are corroboration. Conflicting claims, source-version conflicts, and
current-versus-stale conflicts remain explicit and unresolved.

Only supported facts become findings. Assumptions and gaps remain limitations.
Conflict and weak/stale evidence cap confidence. Recommendations are candidates,
always require human review, and never approve, release, persist, or create
backlog work.

## Canonical boundary

H7 projections are internal and immutable. The public result is projected into
the existing Contracts 1.5.0 `ResearchResult` and validated before return. No
H7-only fields leak into the canonical payload. `ResearchEngine` remains the
single public research result path; the legacy flow remains the default unless
an H7 orchestrator is explicitly composed.

## Non-goals

H7 has no direct HTTP, provider SDK, database, vector-store client, persistence,
source registry, approval mutation, backlog mutation, or `ToolExecutor`. Backend
integration and contract canonicalization remain later handoff work.
