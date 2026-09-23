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
  -> canonical ResearchEvidenceAdmissionPolicy
  -> deterministic EvidenceRelevancePolicy per subquery
  -> deterministic evidence-gap decision
  -> ResearchToolSelectionPolicy
  -> ResearchEvidenceProvider port
  -> deterministic EvidenceQualityPolicy
  -> bounded ResearchClaimExtractor (ModelGateway)
  -> duplicate/corroboration/conflict comparison
  -> FindingRecommendationBuilder
  -> ResearchRecommendationSynthesizer (ModelGateway)
  -> canonical ResearchResult validation
```

The planner emits at most eight typed subqueries. The claim extractor receives
at most twelve evidence items and 12,000 content characters. All model calls
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

Tool cost is also tracked through a conservative local reservation ledger.
Generic tool estimates and external-research estimates are cumulative across
subqueries. A provider call is skipped when the next reservation would exceed
the supplied ceiling or the remaining run-cost estimate. This is defense in
depth only; Backend remains authoritative for actual billing and accounting.

## Relevance and canonical admission

Every ContextBundle, Memory, validated H6 child, and provider item passes the
same `ResearchEvidenceAdmissionPolicy` before claim or recommendation model
input. It validates the canonical EvidenceRef, exact tenant/organization/
workspace identity, scope subset, classification narrowing, VALID status,
external UNTRUSTED semantics, and `instruction_authority=false`. Malformed items
are excluded with explicit limitations; valid siblings may continue.

`EvidenceRelevancePolicy` then assesses each admitted item independently for
each subquery. Explicit matching `subquery_ids` are exact; explicit mismatches
are irrelevant. Untagged evidence uses deterministic lexical overlap, evidence-
need hints, domain evidence hints, and bounded metadata. It uses no embeddings
or vector store. Only EXACT/RELEVANT evidence can satisfy a subquery; WEAK data
may support later analysis, while IRRELEVANT data cannot suppress retrieval.

Relevance and quality remain distinct: high/current but irrelevant evidence
does not establish sufficiency, while relevant stale or low-reliability evidence
remains relevant but receives conservative quality/confidence treatment.

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

Only supported facts become findings. A claim may retain every conflict in which
it participates. Assumptions are mapped only to recommendations whose fact topic
they affect; unrelated assumptions do not lower unrelated confidence.

One shared `ResearchRecommendationSynthesizer` receives only validated findings,
facts, relevant conflicts/assumptions, bounded evidence previews, domain hints,
and the cumulative remaining model budget. Its strict JSON output is checked for
known IDs, fact/evidence traceability, relevance, and prohibited approval or
execution semantics. Recommendations are substantive proposals, always require
human review, and never approve, release, persist, execute, or create backlog
work. If synthesis fails or budget is exhausted, valid findings remain and the
recommendation list is empty with an explicit limitation.

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
