# Struktur Folder

Dokumen ini menjelaskan struktur yang benar-benar tersedia pada baseline GENESIS. Subsystem
yang belum diimplementasikan tidak direpresentasikan sebagai package kosong.

## Folder tingkat atas

- `src/genesis/`: source package service dan seluruh domain GENESIS.
- `blueprints/`: contoh/template deklaratif; bukan generated Python Agent dan bukan state aktif.
- `tests/`: unit, integration, evaluation, regression, dan architecture boundary checks.
- `docs/`: dokumentasi operasional, arsitektur, keputusan, serta reference architecture.
- `.github/`: workflow quality, CODEOWNERS, dan template pull request.

## `src/genesis`

- `control_plane/`: capability factory non-authoritative yang menghasilkan canonical
  CapabilityDraft dan `AgentDraftProposal` tanpa menulis registry atau mengubah lifecycle.
- `capabilities/`: taxonomy capability-first dan resolver terhadap snapshot katalog Backend.
- `agents/`: Blueprint dan typed canonical `AgentDefinition` projection. Runtime aktif berada
  di `runtime/agentic/`; registry/lifecycle authority tetap di ALOS Backend.
- `skills/`: specification, loader, evaluator, runtime, dan selective instruction loading.
- `orchestration/`: satu MCA, authority-safe child delegation, dan workflow Protocol.
- `runtime/`: execution limits, iterative `AgentRuntimeEngine`, scoped context, dan HTTP
  ToolRequest client ke Backend.
- `memory/`: retrieval, ranking, write policy, dan research memory yang tenant-scoped.
- `research/`: canonical application facade pada `engine/` dan internal decomposition,
  evidence, claim, conflict, finding, serta recommendation pipeline pada `orchestration/`.
- `reviews/`: model, package builder, summary, dan Protocol AI review non-authoritative.
- `evals/`: risk profile, versioned regression catalog, domain probes, deterministic runner,
  readiness policy, dan research safety evaluator.
- `model_gateway/`: request/response, policy, budget, routing, dan provider-isolation port.
- `adapters/`: integrasi framework untuk LangGraph, MCP, dan provider ModelGateway.
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
