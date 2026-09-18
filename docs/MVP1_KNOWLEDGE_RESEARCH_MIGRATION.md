# Migrasi Knowledge dan Research MVP-1

Audit memakai snapshot `andara-alos-ai/alos@01416390287114a451a22e16ff14e493df43362f`.
Pada snapshot itu tidak ada modul mandiri `memory/`, `research/`, atau `evidence/`; intelligence
terutama bercampur di `documents/intelligence.py`. Karena itu foundation memory/research baru
dicatat sebagai adaptasi boundary, bukan klaim pemindahan fitur lengkap.

GENESIS kini memiliki:

- `BackendContextProvider` yang membuat `ToolRequest` untuk `source.search_context`;
- ranking context deterministik yang mempertahankan evidence lineage;
- document comparison murni untuk duplicate, conflict, missing field, dan outdated reference;
- `ResearchEngine` yang hanya menggunakan `ContextBundle`, memanggil model melalui
  `ModelGateway`, memvalidasi evidence citation, dan menghasilkan `ResearchResult` kanonis;
- recommendation sebagai backlog candidate, bukan action atau approval.

GENESIS tidak mengimpor Backend, SQLAlchemy, psycopg, atau model persistence bisnis. Alurnya:

```text
GENESIS Research/Memory
  -> ToolRequest
  -> ALOS Backend ToolExecutor
  -> Source/Document/Evidence authority
  -> ContextBundle/ToolResult
  -> GENESIS reasoning melalui ModelGateway
```

Backend tetap menegakkan authorization, scope, classification, storage reference, dan audit.
GENESIS hanya melakukan retrieval orchestration, ranking, analysis, finding, dan recommendation.
Tidak ada provider credential yang diperlukan untuk start atau deterministic test.
