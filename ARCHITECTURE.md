# Arsitektur GENESIS

GENESIS menggunakan arsitektur ports-and-adapters. Domain menyatakan model dan protocol; `adapters/` menghubungkan PydanticAI, LangGraph, MCP, atau provider. Arah dependency selalu dari adapter menuju domain interface.

## Lapisan utama

1. Capability Factory menghasilkan proposal workforce non-authoritative untuk governance Backend.
2. Capability layer memastikan desain capability-first.
3. Generic Agent/Skill runtime mengeksekusi definition berversi.
4. MCA mengoordinasikan business workflow melalui OrchestrationEngine.
5. DelegationGuard menegakkan lineage, authority inheritance, budget, limit, dan cycle prevention.
6. ModelGateway menegakkan policy, budget, routing, dan provider isolation.
7. Research, assurance, dan review menghasilkan evidence, finding, serta recommendation non-authoritative.
8. ALOS Backend menerima ToolRequest dan tetap memiliki seluruh business action.

## Invariant

- Hanya ada satu MCA.
- Control Plane bukan master runtime orchestrator kedua.
- Domain tidak mengimpor framework adapter.
- Agent tidak memanggil provider atau business database langsung.
- AI review tidak menghasilkan approval authoritative.
- Dynamic Agent/Skill menjadi draft data, bukan source code baru.
- Child delegation tidak dapat memperluas authority atau budget.
