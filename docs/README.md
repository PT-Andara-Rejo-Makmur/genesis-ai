# Indeks Dokumentasi genesis-ai

Mulai dari [README repository](../README.md). Panduan runtime mengikuti source
dan contracts terkini; requirements/compatibility bukan klaim seluruh fitur siap.
Bukti tes bertanggal hanya berlaku untuk source dan environment yang dicatat.
Status lintas repository dipusatkan pada [readiness produksi](https://github.com/PT-Andara-Rejo-Makmur/alos-infra/blob/development/docs/PRODUCTION_READINESS_2026-10-04.md).

Authority tetap Web → Backend → GENESIS, dengan Backend sebagai pemilik data,
akses dan keputusan. Secret, dump, log privat dan artifacts lokal tidak masuk Git.

## Runtime dan sistem AI

- [Arsitektur Agent](AGENT_ARCHITECTURE.md)
- [Runtime Agentic dengan Batas Eksekusi](AGENTIC_RUNTIME.md)
- [ARA: Percakapan dan Analisis Berbasis Evidence](business-assistant.md)
- [Cross-Repository Context and Research Contracts](CROSS_REPO_CONTEXT_RESEARCH_CONTRACTS.md)
- [Delegation System](DELEGATION_SYSTEM.md)
- [Pengembangan](DEVELOPMENT.md)
- [Struktur Folder](FOLDER_STRUCTURE.md)
- [Instalasi](INSTALLATION.md)
- [GENESIS Memory Intelligence](MEMORY_SYSTEM.md)
- [Governed production model routing](model-provider-routing.md)
- [Orchestration](ORCHESTRATION.md)
- [Research Orchestration](RESEARCH_ORCHESTRATION.md)
- [Sistem Review](REVIEW_SYSTEM.md)
- [Menjalankan Service](RUNNING.md)
- [Sistem Skill](SKILL_SYSTEM.md)
- [Boundary Eksekusi Tool](TOOL_EXECUTION_BOUNDARY.md)

## Keputusan dan referensi arsitektur

- [ADR-001: Isolasi Framework](adr/ADR-001-framework-isolation.md)
- [ADR-002: Satu MCA](adr/ADR-002-single-mca.md)
- [ADR-003: ModelGateway Tunggal](adr/ADR-003-model-gateway.md)
- [ADR-004: Otoritas Tetap pada ALOS Backend](adr/ADR-004-backend-authority.md)
- [Batas Otoritas](architecture/AUTHORITY_BOUNDARIES.md)
- [Control Plane dan MCA](architecture/CONTROL_PLANE.md)
- [Hermes sebagai Reference Architecture](reference-architectures/hermes.md)
- [Peran LangGraph](reference-architectures/langgraph.md)
- [Peran MCP](reference-architectures/mcp.md)
- [Peran PydanticAI](reference-architectures/pydantic-ai.md)

## Blueprint dan prosedur

- [Boundary blueprint dan Skill packages](../blueprints/README.md)

## Pemeriksaan sebelum commit

Dari sibling checkout Infra, jalankan `python scripts/verify-documentation.py`.
Pemeriksaan memvalidasi link file kelima repository serta casing Linux tanpa jaringan.
