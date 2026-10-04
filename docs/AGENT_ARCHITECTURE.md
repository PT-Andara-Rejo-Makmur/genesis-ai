# Arsitektur Agent

Agent logis merupakan data berversi, bukan satu class Python untuk setiap Agent.
`AgentBlueprint` adalah template; `AgentDefinition` adalah proyeksi definition
canonical; `AgentDraftProposal` adalah proposal Factory untuk governance Backend.
Draft tidak dapat mengaktifkan dirinya sendiri.

## Alur runtime

```text
Requirement -> CapabilityResolver -> CapabilityDraft / AgentDraftProposal
  -> Backend Registry -> human governance -> release ACTIVE
  -> AgentRunRequest + RuntimeAuthorization
  -> AgentRuntimeEngine + AgenticPlanner
  -> ToolRequest -> Backend ToolExecutor -> ToolResult
  -> canonical AgentRunResult -> Backend persistence/audit
```

Factory memakai snapshot katalog Backend dan memilih capability paling sederhana.
Skill, Workflow, Rule, Validator, Report atau Human Task tidak otomatis menjadi Agent.
Definition membawa referensi Skill/tool/permission/scope/model policy; referensi
tersebut merupakan batas kebutuhan, bukan grant authority.

`AgentRuntimeEngine` memakai `AgenticPlanner` iteratif. Tipe `AgentRunInput`,
protocol `AgentRuntime` dan planner satu lintasan lama tidak dipakai. Framework
berada pada adapter; runtime hanya memanggil model melalui ModelGateway dan tool
melalui Backend. GENESIS tidak menerima koneksi business database.

Backend memvalidasi versi ACTIVE, principal, input/output contract, budget dan
lineage. Run/step, human decision, cancellation, registry dan audit authoritative
dipersist Backend. GENESIS menyimpan operational state terbatas selama run, tanpa
private chain-of-thought. Lihat [runtime](AGENTIC_RUNTIME.md),
[delegation](DELEGATION_SYSTEM.md) dan [model routing](model-provider-routing.md).
