# Struktur Folder

Dokumen ini menjelaskan struktur yang benar-benar tersedia pada baseline GENESIS. Folder
domain yang belum memiliki implementasi lengkap tetap memiliki boundary package yang
menyatakan tanggung jawab dan larangan authority-nya.

## Folder tingkat atas

- `src/genesis/`: source package service dan seluruh domain GENESIS.
- `blueprints/`: contoh/template deklaratif; bukan generated Python Agent dan bukan state aktif.
- `tests/`: unit, integration, evaluation, regression, dan architecture boundary checks.
- `docs/`: dokumentasi operasional, arsitektur, keputusan, serta reference architecture.
- `.github/`: workflow quality, CODEOWNERS, dan template pull request.

## `src/genesis`

- `control_plane/`: workforce lifecycle dan capability management. `factory/` memahami
  requirement, menghasilkan canonical CapabilityDraft/AgentDraft, prompt version, evidence
  requirement, serta risk-based test plan tanpa menulis registry; `lifecycle/`, `supervision/`, `evaluation/`, `remediation/`,
  `sustainability/`, dan `governance_intelligence/` memberi boundary untuk fungsi control
  plane. Folder ini bukan MCA kedua dan tidak mengaktifkan draft sendiri.
- `capabilities/`: model taxonomy capability-first pada `models/`; `resolver/` melakukan
  requirement understanding dan matching terhadap snapshot katalog Backend yang read-only;
  `definitions/` dan `discovery/` tetap boundary. Capability tidak otomatis menjadi Agent.
- `agents/`: `definitions/` memisahkan Blueprint, Definition, dan Draft; `runtime/` menyediakan
  generic runtime Protocol; `lifecycle/` menyatakan lifecycle non-authoritative; dan
  `registry_client/` menjadi boundary ke registry authoritative ALOS Backend.
- `skills/`: model specification serta progressive loader pada `loader/`; boundary eksekusi,
  discovery, evaluasi, dan selective instruction loading berada di `runtime/`, `discovery/`,
  `evaluator/`, dan `progressive_loading/`.
- `orchestration/`: satu MCA pada `mca/`; authority-safe child delegation pada `delegation/`;
  workflow Protocol pada `workflows/`; serta boundary `planning/` dan `synthesis/`.
- `runtime/`: `limits/` memiliki ExecutionBudget; `agentic/` memiliki framework-neutral
  `AgentRuntimeEngine`, planning/tool protocols, dan safe failure; `execution/` memiliki HTTP
  client ToolRequest ke Backend; `context/` serta `recovery/` menjaga boundary scoped context
  dan recovery.
- `memory/`: boundary tenant-scoped untuk `retrieval/`, `ranking/`, `learning/`, dan
  `consolidation/`. Learning hanya menghasilkan proposal, bukan perubahan authority otomatis.
- `research/`: model Finding, Recommendation, dan BacklogCandidate; `engine/` memiliki
  document intelligence source-bound dengan prompt/version dan validasi sitasi. Boundary lain
  berada di `sources/`, `evidence/`, `findings/`, dan `recommendations/`. `domains/` membagi
  riset menjadi `technology/`, `property_business/`, `management/`, dan `property_market/`.
- `reviews/`: model dan Protocol AI review, dengan reviewer `business/`, `technical/`,
  `security/`, `evidence/`, dan `cost_risk/`. Hasilnya recommendation/assurance, bukan approval.
- `evals/`: model test profile berbasis risiko; folder `positive/`, `negative/`, `regression/`,
  `security/`, dan `recovery/` memetakan lima taxonomy yang dapat dipilih sesuai risiko.
- `model_gateway/`: request/response dan Protocol gateway; policy, budget, dan routing berada di
  `policy/`, `budget/`, serta `routing/`. `adapters/` di bawah folder ini hanya menyatakan port
  provider; implementasi framework/provider konkret tetap berada di root `adapters/`.
- `adapters/`: satu-satunya lokasi integrasi framework. `pydantic_ai/` memetakan generic Agent
  runtime, `langgraph/` memetakan stateful orchestration, `mcp/` menyiapkan governed
  ToolRequest, dan `providers/` menyediakan implementation boundary ModelGateway.
- `observability/`: correlation ID middleware dan OpenTelemetry API boundary tanpa memaksakan
  exporter tertentu.
- `api/`: typed internal API untuk health, readiness, system information, serta factory
  analysis non-authoritative. Business API authoritative tidak berada di repository ini.
- `config.py`: typed environment settings dan secret-safe configuration.
- `main.py`: FastAPI application factory dan endpoint service foundation.
- `py.typed`: marker type information untuk consumer package.

## `blueprints`

- `agents/`: format blueprint Agent deklaratif sebelum menjadi Definition atau Draft.
- `skills/`: format `skill.yaml` dan `SKILL.md` yang dapat ditemukan secara progresif.
- `workflows/`: template stateful workflow yang membutuhkan orchestration adapter.
- `evaluators/`: profile evaluasi berbasis risiko dan taxonomy yang diperlukan.
- `domain_profiles/`: constraints dan vocabulary domain tanpa menanam business authority.

Setiap folder blueprint saat ini berisi README boundary, bukan contoh production palsu.

## `tests`

- `unit/`: validasi model, factory, resolver, document intelligence, budget, delegation guard,
  ModelGateway, review, dan Skill loader.
- `contract/`: validasi output factory langsung terhadap canonical JSON Schema
  `alos-contracts`.
- `integration/`: startup, endpoint FastAPI, dan AgentRuntimeEngine ke governed HTTP tool
  boundary tanpa provider atau database nyata.
- `evals/`: pemilihan lima taxonomy evaluasi berbasis risiko.
- `regression/`: aturan import framework, larangan direct provider pada Agent, dan single MCA.
- `conftest.py`: konfigurasi test dan helper lintas kategori.

## `docs`

- `architecture/`: control plane dan trust/authority boundary lintas repository.
- `adr/`: keputusan arsitektur yang harus direview ketika boundary berubah.
- `reference-architectures/`: penilaian terhadap Hermes, PydanticAI, LangGraph, dan MCP;
  dokumen ini bukan salinan source project eksternal.
- Dokumen root `docs/`: instalasi, menjalankan service, development, Agent, Skill,
  orchestration, review, dan struktur folder.

## `.github`

- `workflows/`: CI Python 3.12 untuk Ruff, mypy, pytest, architecture checks, dan import app.
- `CODEOWNERS`: placeholder reviewer AI/Backend yang wajib diganti dengan akun/tim organisasi.
- `pull_request_template.md`: checklist perubahan authority, framework, test, dan dokumentasi.
