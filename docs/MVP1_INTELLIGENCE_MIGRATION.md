# Migrasi Intelligence MVP-1

Dokumen ini mencatat hasil Migration Batch 4 dari monorepo MVP-1 pada pinned SHA
`01416390287114a451a22e16ff14e493df43362f`. Source hanya diaudit; tidak diubah.

## Keputusan migrasi

| Area legacy | Keputusan | Implementasi target | Catatan authority |
|---|---|---|---|
| `genesis/agent_designer.py` — requirement mapping, risk, prompt, evidence, test plan | ADAPT/SPLIT | `capabilities/resolver/` dan `control_plane/factory/` | Direct registry, release request, dan persistence tidak dimigrasikan. |
| `genesis/semantic_analysis.py` — source-only prompt dan validasi sitasi | ADAPT | `research/engine/document_intelligence.py` | Hasil selalu `AI_INFERRED`; tidak menjadi business truth. |
| `genesis/document_analysis.py` | ADAPT | Model immutable source dan analisis melalui `ModelGateway` | Source harus berstatus aktif/disetujui serta terikat versi dan SHA-256. |
| `model_gateway/` — policy, budget, routing, provider abstraction | REUSE/ADAPT | `model_gateway/` | Domain tidak mengimpor SDK provider; classification diperiksa sebelum routing. |
| `evals/` — taxonomy dan generator rencana test | ADAPT | `evals/models.py` dan factory risk-based test plan | Negative test memiliki expected status/error; kategori tidak otomatis berarti PASS. |
| AI-side capability matching | ADAPT | `CapabilityResolver` | Hanya memakai snapshot katalog read-only dari Backend. |
| `genesis/router.py` — query registry/database langsung | DO NOT MIGRATE | Snapshot typed `CapabilityCatalogItem` pada request | Agent/Capability/Skill Registry tetap authority Backend. |
| Direct `AgentRegistryRepository` dan `ReleaseGovernanceRepository` pada designer | DO NOT MIGRATE | `RegistryHandoff` non-authoritative | Backend menjalankan registrasi, governance, keputusan, dan release. |
| Chat/history/upload persistence legacy | DEFER | Tidak termasuk batch ini | Ownership dan retention perlu contract/ADR terpisah; tidak boleh menjadi business persistence tersembunyi. |

## Alur final

```text
ALOS Backend
  -> POST /internal/v1/factory/analyze
  -> Requirement + snapshot katalog authoritative
GENESIS
  -> RequirementUnderstanding
  -> CapabilityResolution
  -> canonical CapabilityDraft
  -> optional canonical AgentDefinition dalam AgentDraft proposal
  -> evidence requirements + risk-based test plan
ALOS Backend
  -> Registry / Governance / IT Decision / Director Decision / Release Authority
```

GENESIS tidak menulis registry dan tidak mengubah state authoritative. Field
`handoff.authoritative_state_changed` selalu `false`. `CapabilityDraft` dan
`AgentDefinition` divalidasi terhadap JSON Schema dari `alos-contracts` yang ditunjuk oleh
`ALOS_CONTRACTS_PATH`; tidak ada Python import lintas repository.

## Capability-first

Resolver memilih bentuk paling sederhana: Skill, Workflow, Rule, Validator, Report,
Human Task, Schedule, Event Handler, requirement connector/tool, Agent, atau Composite.
Agent proposal hanya dibuat untuk kebutuhan yang memang memerlukan runtime Agent/Composite.

## Model dan document intelligence

Semua pemanggilan model mengikuti `ModelGateway -> policy -> budget -> route -> adapter`.
Document intelligence menggunakan prompt berversi, sumber bernomor, sitasi baris, batas
60.000 karakter, content SHA-256, dan validation terhadap heading/sitasi. Tidak ada external
research atau tool invocation pada analyzer tersebut.

## Gap yang diketahui

- Endpoint factory sudah typed oleh Pydantic dan output canonical schema, tetapi path
  `/internal/v1/factory/analyze` belum tercantum dalam OpenAPI internal `alos-contracts`.
  Penambahan itu harus dilakukan sebagai perubahan contract terpisah agar source of truth
  tetap berada di repository contracts.
- Provider konkret, runtime persistence, dan production catalog transport tidak diaktifkan
  pada baseline ini. Test memakai adapter deterministic tanpa credential.
- Legacy conversation/upload intelligence belum dimigrasikan karena ownership, retention,
  dan security contract belum dibekukan.
