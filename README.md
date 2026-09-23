# GENESIS AI Control Plane

GENESIS adalah pusat kendali AI tertata kelola untuk ALOS. Repository ini mengimplementasikan Capability Factory non-authoritative, runtime Agent generik, sistem Skill, kecerdasan context dan memory, delegation, kecerdasan research, assurance/review AI deterministik, dan ModelGateway.

GENESIS bukan server autentikasi, otoritas RBAC, pemilik database bisnis, otoritas approval akhir, otoritas rilis, frontend, atau super-agent tanpa batasan.

## Posisi di dalam ALOS

```text
Frontend / ARA / GIIVEPRO
          |
          v
     ALOS Backend  <---- identity, permission, state, decision, release, audit
          |
          | typed internal contract
          v
       GENESIS ----> ModelGateway ----> provider adapter
          |
          | ToolRequest
          v
     ALOS Backend ToolExecutor
```

ALOS Backend tetap menjadi sumber kebenaran. GENESIS melakukan penalaran dan orchestration, tetapi seluruh aksi bisnis, approval, rilis, permission, dan audit authoritative berada di Backend.

## GENESIS Control Plane dan MCA

- **GENESIS Control Plane** menghasilkan proposal draft capability dan Agent untuk governance Backend. Lifecycle, approval, activation, supervision, remediation, dan kendali sustainability tetap berada di Backend atau direncanakan untuk integrasi berikutnya.
- **MCA (AI Master Coordinator)** adalah satu-satunya orchestrator utama runtime bisnis. MCA mengoordinasikan pekerjaan bertahap dan delegation melalui interface orchestration.

Control Plane tidak menjadi orchestrator kedua. MCA tidak mengambil alih lifecycle workforce.

## Cakupan repository

Repository ini memiliki implementasi untuk capability, Agent, Skill, orchestration, delegation, context/batas runtime, kecerdasan memory, research, taxonomy evaluasi, review AI, ModelGateway, serta layanan API internal.

Repository ini tidak memiliki autentikasi pengguna, otoritas kebijakan RBAC, state bisnis, koneksi langsung ke database bisnis, ToolExecutor authoritative, keputusan IT/Director, transisi rilis, atau UI.

## Framework yang disetujui

- **PydanticAI**: dependency framework yang disetujui untuk adapter saat integrasi diperlukan. Runtime aktif tetap berbasis data dan akses model hanya melalui ModelGateway.
- **LangGraph**: adapter untuk workflow bertahap, delegation, pause/resume, state, checkpoint/recovery, dan gerbang manusia. Graph tidak digunakan untuk masalah sederhana.
- **MCP**: adapter interoperabilitas connector di belakang boundary tool tertata kelola.
- **Hermes**: hanya sebagai referensi arsitektur; source code dan model autonomy tidak disalin.
- **PostgreSQL/pgvector**: target persistence untuk runtime/referensi dan arsitektur memory, bukan otoritas database bisnis.

Framework hanya boleh digunakan di `src/genesis/adapters/`. Domain bergantung pada protocol, bukan pada implementasi framework.

## Prasyarat

- Python 3.12
- Git
- Docker opsional
- ALOS Backend dan `alos-contracts` untuk integrasi penuh
- Kredensial provider tidak diperlukan untuk health, readiness, atau rangkaian pengujian

## Instalasi Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,frameworks]"
Copy-Item .env.example .env
```

## Instalasi Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,frameworks]'
cp .env.example .env
```

## Variabel lingkungan

- `APP_ENV`, `APP_HOST`, `APP_PORT`: konfigurasi layanan.
- `ALOS_BACKEND_BASE_URL`: endpoint Backend authoritative.
- `ALOS_INTERNAL_TOKEN`: secret antarlayanan; tidak boleh disimpan ke Git.
- `ALOS_CONTRACTS_PATH`: lokasi checkout `alos-contracts` untuk validasi draft canonical.
- `OTEL_SERVICE_NAME`: nama layanan telemetry.
- `DEFAULT_MODEL_ROUTE`: route ModelGateway; nilai default `disabled` aman tanpa provider.
- `MAX_DELEGATION_DEPTH`, `MAX_DELEGATION_CHILDREN`: batas keras orchestration.

## Menjalankan layanan

```bash
uvicorn genesis.main:app --reload --host 127.0.0.1 --port 8100
```

Endpoint dasar:

- `GET /health`
- `GET /internal/v1/system/integration` untuk diagnostik internal tanpa provider atau database bisnis
- `GET /ready`
- `GET /internal/v1/system/info`
- `POST /internal/v1/factory/analyze` untuk memahami requirement dan menghasilkan draft canonical;
  endpoint ini tidak mendaftarkan, menyetujui, atau merilis capability/Agent.
- `GET /docs`
- `GET /openapi.json`

GENESIS mengirim `ToolRequest` canonical ke `POST /internal/v1/tool-requests` milik Backend melalui
`BackendToolClient`; tidak ada adapter tool bisnis pada GENESIS. Lihat
[Boundary Eksekusi Tool](docs/TOOL_EXECUTION_BOUNDARY.md).

## Pengujian dan gerbang mutu

```bash
ruff check .
mypy
pytest
python -c "from genesis.main import app; assert app.title == 'GENESIS AI Control Plane'"
```

Rangkaian pengujian bersifat deterministik dan tidak memanggil API provider. Pemeriksaan arsitektur menolak impor framework/adapter ke domain dan dependency provider langsung pada domain Agent.

## Docker

```bash
docker build -t genesis-ai:local .
docker run --rm --env-file .env -p 8100:8100 genesis-ai:local
```

Container berjalan sebagai pengguna non-root. Konfigurasi provider, exporter telemetry, serta target persistence disediakan oleh deployment.

## Sistem Agent

Agent tidak direpresentasikan sebagai satu class Python untuk setiap Agent logis. Ratusan Agent menggunakan runtime generik melalui alur `Blueprint -> Definition -> Runtime -> Run`. Agent dinamis menghasilkan `AgentDraftProposal` tervalidasi untuk serah terima governance, bukan file `.py` atau aktivasi mandiri.

Capability Factory menjalankan alur `Requirement -> CapabilityResolver -> CapabilityDraft ->
optional AgentDraftProposal -> Backend Registry/Governance`. Katalog capability pada request adalah
snapshot hanya-baca dari Backend. Output canonical divalidasi terhadap `alos-contracts` tanpa
impor Python lintas repository.

## Sistem Skill

Skill menggunakan ALOS Skill Specification pada `skill.yaml` dan prosedur pada `SKILL.md`. Discovery hanya membaca metadata; instruksi penuh dimuat ketika relevan. Skill yang dibuat sistem selalu menjadi `SkillDraft` yang memerlukan review dan activation dari otoritas ALOS.

## Orchestration dan delegation

Eksekusi Agent menggunakan `AgentRuntimeEngine` dengan `AgenticPlanner` iteratif. LangGraph hanya dipilih ketika workflow bertahap dan stateful memang diperlukan. Delegation mempertahankan `root_run_id`, `parent_run_id`, depth, serta pewarisan permission/scope/tool/budget dan mencegah cycle maupun perluasan kewenangan.

## Boundary model dan tool

Agent hanya mengakses model melalui alur `Agent -> ModelGateway -> policy -> budget -> route -> provider adapter`. Agent tidak mengimpor provider SDK.

Aksi bisnis mengikuti `Agent -> ToolRequest -> ALOS Backend -> ToolExecutor -> ToolResult`. MCP tidak boleh menjadi jalur pintas untuk melewati Backend.

Runtime generik berada pada `AgentRuntimeEngine`: komponen ini mengonsumsi context dan snapshot
authorization dari Backend, menjalankan perencanaan melalui protocol, menerapkan budget eksekusi,
dan menghasilkan `AgentRunResult` canonical. Otoritas run dan persistence tidak berada di
GENESIS. Lihat [Split Runtime MVP-1](docs/MVP1_RUNTIME_SPLIT.md).

## Alur kerja pengembangan

1. Modelkan capability sebelum memutuskan bahwa implementasinya harus berupa Agent.
2. Tambahkan domain model/protocol tanpa import framework.
3. Tempatkan integrasi framework atau provider hanya di `adapters/`.
4. Tambahkan taxonomy pengujian berbasis risiko.
5. Jalankan seluruh gerbang mutu dan dokumentasikan perubahan authority/budget/delegation.

Dokumentasi: [Arsitektur](ARCHITECTURE.md), [Struktur Folder](docs/FOLDER_STRUCTURE.md), [Arsitektur Agent](docs/AGENT_ARCHITECTURE.md), [Migrasi Intelligence MVP-1](docs/MVP1_INTELLIGENCE_MIGRATION.md), [Migrasi Knowledge dan Research MVP-1](docs/MVP1_KNOWLEDGE_RESEARCH_MIGRATION.md), [Sistem Skill](docs/SKILL_SYSTEM.md), [Orchestration](docs/ORCHESTRATION.md), dan [Sistem Review](docs/REVIEW_SYSTEM.md).
