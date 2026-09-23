# Struktur Folder

Dokumen ini menjelaskan struktur yang benar-benar tersedia pada baseline GENESIS. Subsistem
yang belum diimplementasikan tidak direpresentasikan sebagai package kosong.

## Folder tingkat atas

- `src/genesis/`: source package layanan dan seluruh domain GENESIS.
- `blueprints/`: contoh/template deklaratif; bukan Agent Python hasil generasi dan bukan state aktif.
- `tests/`: pengujian unit, integrasi, evaluasi, regresi, dan boundary arsitektur.
- `docs/`: dokumentasi operasional, arsitektur, keputusan, serta referensi arsitektur.
- `.github/`: workflow gerbang mutu, CODEOWNERS, dan template pull request.

## `src/genesis`

- `control_plane/`: Capability Factory non-authoritative yang menghasilkan `CapabilityDraft`
  dan `AgentDraftProposal` canonical tanpa menulis registry atau mengubah lifecycle.
- `capabilities/`: taxonomy yang mengutamakan capability dan resolver terhadap snapshot katalog Backend.
- `agents/`: `Blueprint` dan proyeksi `AgentDefinition` canonical bertipe. Runtime aktif berada
  di `runtime/agentic/`; otoritas registry/lifecycle tetap di ALOS Backend.
- `skills/`: specification, loader, evaluator, runtime, dan pemuatan instruksi selektif.
- `orchestration/`: satu MCA, delegation anak yang aman terhadap kewenangan, dan protocol workflow.
- `runtime/`: batas eksekusi, `AgentRuntimeEngine` iteratif, context terlingkup, dan client HTTP
  `ToolRequest` menuju Backend.
- `memory/`: retrieval, ranking, kebijakan penulisan, dan memory research yang terlingkup tenant.
- `research/`: facade aplikasi canonical pada `engine/` dan pipeline internal untuk decomposition,
  evidence, claim, conflict, finding, serta recommendation pada `orchestration/`.
- `reviews/`: model, penyusun package, ringkasan, dan protocol review AI non-authoritative.
- `evals/`: profil risiko, katalog regresi berversi, probe domain, runner deterministik,
  kebijakan readiness, dan evaluator keamanan research.
- `model_gateway/`: request/response, policy, budget, routing, dan port isolasi provider.
- `adapters/`: integrasi framework untuk LangGraph, MCP, dan provider ModelGateway.
- `observability/`: middleware correlation ID dan boundary API OpenTelemetry tanpa memaksakan
  exporter tertentu.
- `api/`: API internal bertipe untuk health, readiness, informasi sistem, serta analisis Factory
  non-authoritative. API bisnis authoritative tidak berada di repository ini.
- `config.py`: pengaturan environment bertipe dan konfigurasi yang aman terhadap secret.
- `main.py`: Factory aplikasi FastAPI dan endpoint dasar layanan.
- `py.typed`: penanda informasi tipe untuk package pengguna.

## `blueprints`

- `agents/`: format blueprint Agent deklaratif sebelum menjadi Definition atau Draft.
- `skills/`: format `skill.yaml` dan `SKILL.md` yang dapat ditemukan secara progresif.
- `workflows/`: template workflow stateful yang membutuhkan adapter orchestration.
- `evaluators/`: profil evaluasi berbasis risiko dan taxonomy yang diperlukan.
- `domain_profiles/`: constraint dan kosakata domain tanpa menanam kewenangan bisnis.

Setiap folder blueprint saat ini berisi README boundary, bukan contoh produksi palsu.

## `tests`

- `unit/`: validasi model, Factory, resolver, kecerdasan dokumen, budget, delegation guard,
  ModelGateway, review, dan loader Skill.
- `contract/`: validasi output Factory langsung terhadap JSON Schema canonical
  `alos-contracts`.
- `integration/`: startup, endpoint FastAPI, dan `AgentRuntimeEngine` ke tool HTTP tertata kelola
  boundary tanpa provider atau database nyata.
- `evals/`: pemilihan lima taxonomy evaluasi berbasis risiko.
- `regression/`: aturan impor framework, larangan provider langsung pada Agent, dan MCA tunggal.
- `conftest.py`: konfigurasi pengujian dan helper lintas kategori.

## `docs`

- `architecture/`: Control Plane dan boundary trust/authority lintas repository.
- `adr/`: keputusan arsitektur yang harus direview ketika boundary berubah.
- `reference-architectures/`: penilaian terhadap Hermes, PydanticAI, LangGraph, dan MCP;
  dokumen ini bukan salinan source project eksternal.
- Dokumen root `docs/`: instalasi, menjalankan layanan, pengembangan, Agent, Skill,
  orchestration, review, dan struktur folder.

## `.github`

- `workflows/`: CI Python 3.12 untuk Ruff, mypy, pytest, pemeriksaan arsitektur, dan impor aplikasi.
- `CODEOWNERS`: placeholder reviewer AI/Backend yang wajib diganti dengan akun/tim organisasi.
- `pull_request_template.md`: checklist perubahan kewenangan, framework, pengujian, dan dokumentasi.
