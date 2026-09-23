# Arsitektur GENESIS

GENESIS menggunakan arsitektur ports-and-adapters. Domain menyatakan model dan protocol;
`adapters/` menghubungkan PydanticAI, LangGraph, MCP, atau provider. Arah dependency selalu
dari adapter menuju interface domain.

## Lapisan utama

1. Capability Factory menghasilkan proposal workforce non-authoritative untuk governance Backend.
2. Lapisan capability memastikan desain yang mengutamakan capability.
3. Runtime Agent/Skill generik mengeksekusi definition berversi.
4. MCA mengoordinasikan workflow bisnis melalui `OrchestrationEngine`.
5. `DelegationGuard` menegakkan lineage, pewarisan kewenangan, budget, batas, dan pencegahan cycle.
6. `ModelGateway` menegakkan policy, budget, routing, dan isolasi provider.
7. Research, assurance, dan review menghasilkan evidence, finding, serta recommendation non-authoritative.
8. ALOS Backend menerima `ToolRequest` dan tetap memiliki seluruh aksi bisnis.

## Invarian

- Hanya ada satu MCA.
- Control Plane bukan orchestrator utama runtime kedua.
- Domain tidak mengimpor adapter framework.
- Agent tidak memanggil provider atau database bisnis secara langsung.
- Review AI tidak menghasilkan approval authoritative.
- Agent/Skill dinamis menjadi data draft, bukan source code baru.
- Delegation anak tidak dapat memperluas kewenangan atau budget.
