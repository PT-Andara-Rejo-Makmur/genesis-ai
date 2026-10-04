# Orchestration

Satu `MasterCoordinator` mengoordinasikan business work melalui
`OrchestrationEngine`. Capability Factory menghasilkan draft untuk governance;
Factory bukan orchestrator kedua atau pemilik lifecycle workforce.

Eksekusi Agent memakai `AgentRuntimeEngine` dan planner iteratif. Adapter LangGraph
tersedia untuk workflow yang membutuhkan state/checkpoint; keberadaan adapter
tidak membuktikan durable workflow atau integrasi production tertentu.

Delegation menjaga run/root/parent lineage, tenant/workspace, subset permission,
scope, tool, classification, depth, child count, concurrency, budget dan cycle
prevention. Human gates diselesaikan Backend. GENESIS memvalidasi snapshot sebagai
defense in depth dan tidak memperluas authority.

Run, cancellation, audit, registry dan keputusan authoritative dipersist Backend.
Lihat [runtime](AGENTIC_RUNTIME.md), [delegation](DELEGATION_SYSTEM.md) dan
[batas authority](architecture/AUTHORITY_BOUNDARIES.md).
