# Split Runtime MVP-1

Audit menggunakan branch `develop` pada pinned SHA
`01416390287114a451a22e16ff14e493df43362f`. Legacy
`services/platform/src/alos/runtime/service.py` menggabungkan reasoning, ModelGateway,
direct ToolExecutor, PostgreSQL run persistence, budget reservation, permission/lifecycle
checks, source evidence, dan audit dalam satu service. File tersebut tidak disalin utuh.

## Ownership GENESIS

`AgentRuntimeEngine` adalah runtime generic dan framework-neutral. Engine bertanggung jawab
atas planning port, schema input/output, execution limit, model invocation melalui
ModelGateway, konsumsi ExecutionContext, serta penyusunan ToolRequest. PydanticAI,
LangGraph, dan Hermes tidak diimpor oleh runtime core.

Engine memerlukan `RuntimeAuthorization` yang berasal dari Backend. Token ini hanya snapshot
run/lifecycle dan tidak menambah authority. Tool harus lolos tiga batas sebelum dikirim:
requested pada AgentRunRequest, diizinkan AgentDefinition, dan diizinkan Backend snapshot.

```text
Backend-authorized AgentRunRequest
  -> AgentRuntimeEngine
  -> RuntimePlanner
  -> ToolRequest
  -> Backend internal HTTP API
  -> ToolExecutor
  -> ToolResult
  -> ModelGateway
  -> canonical AgentRunResult
```

Tool failure, timeout, budget violation, schema violation, dan lifecycle mismatch menjadi
structured failed AgentRunResult. GENESIS tidak menyimpan run authority, tidak mengeksekusi
adapter tool, dan tidak mengakses business database.

## Adaptasi behavior MVP-1

- Schema validation dipertahankan melalui canonical `alos-contracts`.
- Budget token, cost, steps, tool calls, dan timeout dipertahankan secara deterministic.
- `correlation_id` diteruskan dari ExecutionContext ke ToolRequest, ToolResult, ModelGateway,
  dan AgentRunResult.
- Direct in-process `ToolExecutor` dihapus dari runtime intelligence.
- Lifecycle dan permission authority dipindahkan ke Backend; GENESIS hanya memverifikasi
  authorization snapshot sebelum reasoning.
- Provider/model tetap hanya dapat dipanggil melalui ModelGateway.

Lihat test integrasi `tests/integration/test_agent_runtime_engine.py` untuk runtime-to-tool
HTTP flow tanpa provider credential.
