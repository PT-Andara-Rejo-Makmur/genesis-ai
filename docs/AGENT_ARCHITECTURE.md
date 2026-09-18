# Arsitektur Agent

## Blueprint

Blueprint adalah template desain reusable: tujuan umum, capability, dan skill default. Blueprint bukan Agent aktif.

## Definition

AgentDefinition merupakan konfigurasi data berversi berisi purpose, capability, Skill, tool restriction, permission/scope reference, dan model policy. Ratusan logical Agent menggunakan generic definition yang sama tanpa class Python khusus.

## Draft

AgentDraft adalah proposal Definition yang dibuat manusia atau GENESIS. Draft hanya dapat berstatus `DRAFT` atau `SUBMITTED_FOR_REVIEW`; GENESIS tidak dapat mengaktifkannya sendiri.

Factory menerima requirement dan snapshot katalog read-only dari Backend. Resolver lebih dulu
memilih tipe capability. AgentDraft hanya dibuat bila kebutuhan benar-benar memerlukan Agent
atau Composite; Report, Validator, Workflow, atau Skill tidak otomatis dibungkus Agent.

## Runtime

AgentRuntime adalah Protocol framework-neutral. PydanticAI berada pada adapter dan menerima invoker yang menggunakan ModelGateway. Runtime tidak menerima provider credential atau koneksi business database.

## Run

AgentRunInput membawa `run_id`, `root_run_id`, optional `parent_run_id`, tenant/workspace, correlation, payload, dan budget. Hasil run membawa output state dan evidence reference, bukan approval authoritative.

```text
AgentBlueprint -> AgentDefinition/AgentDraft -> AgentRuntime -> AgentRunResult
                                               |
                                               v
                                         ModelGateway
```

Setelah draft dibuat, GENESIS mengembalikan typed handoff ke Backend. Agent Registry,
Capability Registry, Skill Registry, governance decision, dan release transition tidak pernah
dijalankan oleh factory GENESIS.
