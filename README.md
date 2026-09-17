# GENESIS AI Control Plane

GENESIS adalah Governed AI Control Plane untuk ALOS. Repository ini mengelola capability factory, workforce lifecycle, generic Agent runtime, Skill system, context dan memory intelligence, multi-agent orchestration, delegation, research, evaluation, AI review, supervision, remediation, sustainability intelligence, dan ModelGateway.

GENESIS bukan authentication server, RBAC authority, pemilik business database, final approval authority, release authority, frontend, atau unrestricted super-agent.

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

ALOS Backend tetap source of truth. GENESIS melakukan reasoning dan orchestration, tetapi seluruh aksi bisnis, approval, release, permission, dan authoritative audit berada di Backend.

## GENESIS Control Plane dan MCA

- **GENESIS Control Plane** mengelola lifecycle digital workforce: capability proposal, Agent/Skill draft, evaluation, supervision, remediation, dan sustainability recommendation.
- **MCA (AI Master Coordinator)** adalah satu-satunya master runtime business orchestrator. MCA mengoordinasikan pekerjaan multi-step dan delegation melalui interface orchestration.

Control Plane tidak menjadi orchestrator kedua. MCA tidak mengambil alih workforce lifecycle.

## Cakupan repository

Repository ini memiliki domain dan interface untuk capability, Agent, Skill, orchestration, delegation, runtime context/limit/recovery, memory intelligence, research, evaluation taxonomy, AI review, ModelGateway, framework adapter, serta service API internal.

Repository ini tidak memiliki user authentication, RBAC policy authority, business state, direct business database connection, ToolExecutor authoritative, keputusan IT/Director, release transition, atau UI.

## Framework yang disetujui

- **PydanticAI**: adapter generic Agent runtime. Agent tetap data-driven dan akses model harus melalui ModelGateway-backed invoker.
- **LangGraph**: adapter untuk workflow multi-step, delegation, pause/resume, state, checkpoint/recovery, dan human gate. Graph tidak digunakan untuk masalah sederhana.
- **MCP**: adapter interoperabilitas connector di belakang governed tool boundary.
- **Hermes**: reference architecture saja; source code dan autonomy model tidak disalin.
- **PostgreSQL/pgvector**: target persistence untuk runtime/reference dan memory architecture, bukan business database authority.

Framework hanya boleh digunakan di `src/genesis/adapters/`. Domain bergantung pada protocol, bukan implementasi framework.

## Prasyarat

- Python 3.12
- Git
- Docker opsional
- ALOS Backend dan `alos-contracts` untuk integrasi penuh
- Provider credential tidak diperlukan untuk health, readiness, atau test suite

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

## Environment variable

- `APP_ENV`, `APP_HOST`, `APP_PORT`: konfigurasi service.
- `ALOS_BACKEND_BASE_URL`: endpoint authoritative Backend.
- `ALOS_INTERNAL_TOKEN`: secret service-to-service; tidak boleh disimpan ke Git.
- `OTEL_SERVICE_NAME`: nama telemetry service.
- `DEFAULT_MODEL_ROUTE`: route ModelGateway; default `disabled` aman tanpa provider.
- `MAX_DELEGATION_DEPTH`, `MAX_DELEGATION_CHILDREN`: hard limit orchestration.

## Menjalankan service

```bash
uvicorn genesis.main:app --reload --host 127.0.0.1 --port 8100
```

Endpoint foundation:

- `GET /health`
- `GET /ready`
- `GET /internal/v1/system/info`
- `GET /docs`
- `GET /openapi.json`

## Pengujian dan quality gate

```bash
ruff check .
mypy
pytest
python -c "from genesis.main import app; assert app.title == 'GENESIS AI Control Plane'"
```

Test suite deterministic dan tidak memanggil provider API. Architecture checks menolak import framework/adapters ke domain dan direct provider dependency pada Agent domain.

## Docker

```bash
docker build -t genesis-ai:local .
docker run --rm --env-file .env -p 8100:8100 genesis-ai:local
```

Container berjalan sebagai non-root. Provider configuration, telemetry exporter, serta persistence target disediakan oleh deployment.

## Sistem Agent

Agent tidak direpresentasikan sebagai satu Python class per logical Agent. Ratusan Agent menggunakan generic runtime melalui alur `Blueprint -> Definition/Draft -> Runtime -> Run`. Dynamic Agent menghasilkan data `AgentDraft`, bukan file `.py` atau self-activation.

## Sistem Skill

Skill menggunakan ALOS Skill Specification pada `skill.yaml` dan prosedur pada `SKILL.md`. Discovery hanya membaca metadata; instruksi penuh dimuat ketika relevan. Self-created Skill selalu menjadi `SkillDraft` yang memerlukan review dan activation dari ALOS authority.

## Orchestration dan delegation

Agent execution sederhana menggunakan AgentRuntime. LangGraph hanya dipilih ketika stateful multi-step workflow memang diperlukan. Delegation mempertahankan `root_run_id`, `parent_run_id`, depth, serta inheritance permission/scope/tool/budget dan mencegah cycle maupun authority expansion.

## Model dan tool boundary

Agent hanya mengakses model melalui alur `Agent -> ModelGateway -> policy -> budget -> route -> provider adapter`. Agent tidak mengimpor provider SDK.

Aksi bisnis mengikuti `Agent -> ToolRequest -> ALOS Backend -> ToolExecutor -> ToolResult`. MCP tidak boleh menjadi jalur pintas untuk melewati Backend.

## Development workflow

1. Modelkan capability sebelum memutuskan bahwa implementasinya harus berupa Agent.
2. Tambahkan domain model/protocol tanpa import framework.
3. Tempatkan integrasi framework atau provider hanya di `adapters/`.
4. Tambahkan test taxonomy berbasis risiko.
5. Jalankan seluruh quality gate dan dokumentasikan perubahan authority/budget/delegation.

Dokumentasi: [Arsitektur](ARCHITECTURE.md), [Struktur Folder](docs/FOLDER_STRUCTURE.md), [Arsitektur Agent](docs/AGENT_ARCHITECTURE.md), [Sistem Skill](docs/SKILL_SYSTEM.md), [Orchestration](docs/ORCHESTRATION.md), dan [Sistem Review](docs/REVIEW_SYSTEM.md).
