# Governed production model routing

ARA Web → ALOS Backend → GENESIS AgentRuntimeEngine → GovernedModelGateway → policy →
StaticModelRouter → NineRouterProviderAdapter → the existing external 9Router.
Business reads return through BackendToolClient → Backend ToolExecutor → canonical domain → PostgreSQL.
GENESIS has no business DATABASE_URL. Neither Backend nor Browser receives the router credential.
No 9Router container, installation, provider SDK, provider fallback, Hermes, or connector is included.

The adapter implements ModelProviderAdapter. It sends non-streaming `POST /chat/completions`
with only `model`, `messages`, `max_tokens`, and `stream=false`. Run identity, policy, purpose,
classification, and diagnostics remain local. 9Router owns underlying providers, accounts,
combos, quota routing, and model fallback. The adapter has no business or approval policy.
The API format follows the [9Router chat API](https://github.com/decolua/9router/blob/master/skills/9router-chat/SKILL.md).

## Runtime configuration and ownership

GENESIS alone receives these environment variables:

```dotenv
DEFAULT_MODEL_ROUTE=nine_router
NINE_ROUTER_BASE_URL=http://103.93.135.49:20128/v1
NINE_ROUTER_API_KEY=
NINE_ROUTER_TIMEOUT_SECONDS=10
NINE_ROUTER_MODEL_DEFAULT=
NINE_ROUTER_MODEL_FAST=
NINE_ROUTER_MODEL_STANDARD=
NINE_ROUTER_MODEL_REASONING=
NINE_ROUTER_MODEL_CODING=
NINE_ROUTER_MODEL_CRITICAL=
NINE_ROUTER_MAXIMUM_CLASSIFICATION=INTERNAL
```

Inject the key through the deployment environment or secret manager. Do not put it in a
Dockerfile, image, Git, shell transcript, request trace, or browser configuration. The typed
secret is excluded from settings repr. Base URLs reject userinfo, query, and fragment.
Changing to HTTPS or a private endpoint needs only an environment change.

`DEFAULT_MODEL_ROUTE=disabled` is the configuration kill switch and selects the existing
DisabledProviderAdapter. GENESIS code defaults to disabled. Staging/production Infra config
selects nine_router but leaves its key blank, so readiness remains MISCONFIGURED until configured.
Local/integration config defaults to disabled. No production failure falls back to a test answer.

The current public HTTP endpoint provides no transport encryption: bearer credentials and
authorized business context can be observed on that network path. Deployment should move to
HTTPS or a protected private transport. Authorization headers and sensitive messages are never logged.

## Discovery, readiness, and routing

Authenticated internal `GET /internal/v1/models/readiness` performs `GET {base}/models` with
the operator-supplied Bearer credential. It reports configured/reachable/authenticated/model_selected
and CONNECTED, MISCONFIGURED, UNAVAILABLE, AUTH_FAILED, or MODEL_SELECTION_REQUIRED.
Model IDs are internal diagnostics; Backend projects only `production_provider_connected`.
Web renders Terhubung/Belum Terhubung from that projection. This check depends on the router's
authentication contract; the optional completion smoke verifies actual inference access as well.

Selection is: policy-specific override → configured default → exactly one discovered usable ID.
Configured IDs must exist in discovery. Multiple IDs without an applicable mapping require an
operator choice; no model is selected by position or invented. Model IDs never enter AgentDefinition.

| Existing/production policy | Override | Route |
| --- | --- | --- |
| ara.production, policy.standard | NINE_ROUTER_MODEL_STANDARD | nine_router |
| policy.fast | NINE_ROUTER_MODEL_FAST | nine_router |
| policy.reasoning, policy.evidence-bound-research.v1 | NINE_ROUTER_MODEL_REASONING | nine_router |
| policy.coding | NINE_ROUTER_MODEL_CODING | nine_router |
| policy.critical | NINE_ROUTER_MODEL_CRITICAL | nine_router |
| ara.deterministic | Explicit TEST composition only | ara.deterministic |

Classification is enforced before any provider HTTP. The production ceiling defaults to INTERNAL;
the request cannot raise that ceiling. Unknown policies are rejected before discovery/inference.

## Execution and authority

The canonical modes remain TEST and NORMAL. TEST requires ENABLE_TEST_RUNTIME and a development/test
environment and continues to use DeterministicBusinessAdapter. NORMAL uses the real provider through
the existing gateway and requires Backend-issued ACTIVE authorization and an immutable matching digest.
Research also receives Backend-selected TEST/NORMAL and uses the same production gateway.
CapabilityFactory currently performs deterministic draft analysis; it needs no extra model client.

Production ARA uses an existing authorized, released ACTIVE `ara.workspace-assistant` definition in
the tenant/organization/workspace registry. Exactly one authorized released version must exist.
It must use a production policy, include business.question_answering, only canonical business read tools,
and a finite execution budget (tokens, steps, tool calls, timeout). Its rights and budget intersect
the Principal and ARA limits; they never expand caller authority. Governed research delegation also
requires a released ACTIVE `ara.business-reader` with a compatible narrowed budget/authority envelope.
Provider credentials never register, approve, release, or activate either definition. Use the existing
human review/release workflow if these definitions are not already released. Factory proposals remain DRAFT.

Production planner output is strict AgenticDecision JSON. For factual ARA FINISH, the model returns
claims `{tool_id, pointer, value}` over current observations and the complete admitted evidence ID set.
GENESIS compares each JSON value/type with canonical data, requires coverage of every requested source,
and renders the verified values. Free-form factual prose is not accepted. Authority metadata is removed
from provider observations. Null displays —; successful empty displays Belum ada data; unavailable
displays Belum Terhubung. Owner failure remains FAILED and identifies the failed tool.
Evidence admission still validates tenant/org/workspace, scope, classification, run/correlation,
CURRENT/VALID freshness, captured_at, content_hash, and instruction_authority=false.

Model-generated tool intents pass the existing requested/definition/runtime/context/registry
intersection and Backend argument validation. Unknown/admin tools and forged SQL fail closed.
Business notes, documents, history, and tool content are DATA. Material/task/factory requests are
handled by the planner's governance guard as NEEDS_REVIEW proposals with executed=false; no model can
perform payment, approval, pricing activation, or registry activation.

Production research validates current evidence and exact run lineage, removes the operational
authority envelope from model context, binds output IDs to the run, and renders factual findings from
canonical source values. Model recommendations are explicitly advisory, AI-authored, NEEDS_REVIEW,
and never executable decisions. Recommendations must cite existing findings. Missing finding domain
is supplied from the authoritative research request, so persistence does not rely on optional model fields.

## Failure, budgets, and telemetry

Typed safe codes distinguish configuration, authentication, rate limit, timeout, router unavailable,
invalid request/response, model unavailable/selection, and unavailable token usage. Errors exclude raw
HTTP bodies, headers, credentials, and chained HTTP exceptions. Redirects and ambient proxies are disabled.

There are at most two transport attempts, with a 100ms bounded delay. Retry applies to connection
failure before inference, 429/502/503/504, and discovery transport failure. POST read timeout or ambiguous
network reset is not repeated because inference may already have run. 400/401/403/404/422 and 500 are
not retried. Each attempt has a configurable timeout; runtime's cumulative deadline also remains enforced.
If a retry follows an HTTP failure of a completion POST, even a subsequent 200 cannot certify the
earlier attempt's usage. It fails as PROVIDER_USAGE_UNAVAILABLE before output is admitted. A retry
after a pre-inference connection failure can succeed normally. No previous attempt is counted as free.

Provider prompt_tokens/completion_tokens are required nonnegative integers. Missing/invalid usage fails
before model output/tool intent can be admitted; no tokenizer estimate or fake 0 is reported.
Runtime marks token telemetry UNAVAILABLE and omits token numbers after an ambiguous/unmetered inference.
The gateway checks reported total tokens and any authoritative cost before admitting output; the runtime
also enforces cumulative usage and child reservations. A finite token budget is mandatory.

Cost is None unless the response supplies a finite nonnegative cost. Unknown cost is not reported as 0:
runtime emits cost_telemetry=UNAVAILABLE and omits estimated_cost. Known costs still enforce monetary
limits. When cost cannot be verified, the finite token budget, bounded steps/tool calls, and deadline are
the enforced bounds; monetary spend cannot be certified. Keep quotas/spend enforcement at 9Router too.
Provider request IDs come from the body or x-request-id, otherwise None. Logs contain only local IDs,
route, safe status, reported token counts/request ID, and elapsed latency; they exclude messages/headers.

## Verification and operator handoff

Normal Ruff/Mypy/Pytest and Infra integration are offline and need no router key. Provider tests use
httpx.MockTransport with randomly generated synthetic fixture secrets. GENESIS production runtime tests
use actual Backend AgentRunAuthority, ToolExecutor, and BusinessReadAdapter; Infra additionally exercises
authenticated ASGI boundaries and real PostgreSQL, isolation, evidence, memory, governed child cancellation,
draft proposals, research, and outage/malformed/admin/fabricated-model responses.

Optional, from genesis-ai with the deployment environment already loaded:

```text
python scripts/model-provider-smoke.py
```

No key prints CREDENTIAL_PENDING and performs no HTTP. With a key, this discovers model IDs,
reports selection readiness, and runs one small governed chat completion. If discovery returns multiple
IDs, set NINE_ROUTER_MODEL_DEFAULT or the appropriate policy override to an actually discovered ID.
The smoke prints only safe telemetry, never the key or full model content.

After operator configuration, run live ARA acceptance against disposable/staging data: Sales read,
Executive multi-source summary and research, Sales→Finance denial, material proposals, injection-as-data,
unknown tool rejection, router outage, malformed decisions, persistence, and evidence lineage.
Do not declare READY based on mock tests or a connectivity completion alone. No live key/model IDs were
provided in this implementation task, so real inference and live ARA acceptance remain credential pending.
