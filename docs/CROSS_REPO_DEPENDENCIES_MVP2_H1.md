# CROSS_REPO_DEPENDENCY — MVP2 H1 AI

GENESIS tetap hanya menghasilkan proposal. Dependency berikut harus diselesaikan pada
repository pemilik sebelum H1 dapat dinyatakan terintegrasi penuh.

## CRD-H1-01 — CapabilityDraft canonical fields

- Owner: `alos-contracts` + `alos-backend`
- Contract: `schemas/capability/capability-draft.schema.json`
- Dibutuhkan: canonical `version`, `scope_refs`, `tool_ids`/`backing_tool_ids`,
  `permission_refs`, `prohibited_actions`, `risk_level`, `evidence_requirements`, dan
  `test_requirements` dengan lifecycle/output state `DRAFT`.
- Kondisi saat ini: GENESIS memvalidasi payload yang didukung schema canonical dan mengirim
  field proposal tambahan pada `capability_specification`. Projection ini non-authoritative
  dan tidak menggantikan contract canonical.

## CRD-H1-02 — AgentDraft scope/lifecycle contract

- Owner: `alos-contracts` + `alos-backend`
- Contract: `schemas/agent/agent-definition.schema.json` dan/atau schema `AgentDraft` baru.
- Dibutuhkan: scope proposal dan lifecycle draft yang eksplisit pada contract canonical.
- Kondisi saat ini: `AgentDefinition` tetap divalidasi secara canonical; scope dan detail
  proposal berada pada envelope `StructuredAgentProposal.specification`, sedangkan
  `output_state` selalu `DRAFT` dan `approval_required` selalu `true`.

## CRD-H1-03 — Factory internal API

- Owner: `alos-contracts` + `alos-backend`
- API: `POST /internal/v1/factory/analyze` pada
  `openapi/internal/genesis-internal-api.yaml`, termasuk request, response, structured error,
  auth internal, dan correlation ID.
- Kondisi saat ini: endpoint GENESIS sudah internal dan typed, tetapi belum menjadi bagian
  OpenAPI canonical. Backend harus menjadi caller dan pemilik registry/governance handoff.

Tidak ada workaround berupa business database access, registry lokal, ToolExecutor lokal,
self-approval, self-release, atau permission/scope mutation di `genesis-ai`.
