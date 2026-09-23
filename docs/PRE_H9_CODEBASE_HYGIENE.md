# Kebersihan Basis Kode Pra-H9

## Titik acuan dan cakupan

Pembersihan ini dimulai dari `cf3c8789dfc6d9c1b6daf57d9cd96be521870c56` pada
cabang `development`. Cakupannya terbatas pada penamaan permanen, kepemilikan tipe,
penghapusan kompatibilitas usang, struktur package, pengorganisasian assurance, pengujian,
dan dokumentasi arsitektur terkini. Perubahan ini tidak menambahkan fitur H9 serta tidak
mengubah kebijakan kewenangan maupun kecerdasan.

## Kebijakan penamaan

Identifier produksi permanen menjelaskan semantik produk, bukan tonggak pelaksanaan proyek.
Kebijakan riset menggunakan `policy.research.*`; kasus assurance menggunakan `assurance.*`;
proposal regresi inti menggunakan `CORE_AI_ASSURANCE_REGRESSION_SET`; dan batas model riset
menggunakan `DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET`. Dokumen serah terima dan bukti rilis
historis tetap mempertahankan kosakata tonggak aslinya.

## Kebijakan tipe canonical dan internal

- `AgentDefinition` adalah proyeksi runtime bertipe yang menggunakan kosakata field canonical,
  seperti `skill_refs`, `tool_ids`, `permission_refs`, `scope_refs`, `model_policy_ref`, dan
  `delegation_policy`. Validasi JSON Schema canonical tetap dilakukan pada boundary aplikasi.
- `AgentDraftProposal` adalah satu-satunya proyeksi draft untuk serah terima Factory dan
  governance. Tipe ini tetap non-authoritative dan divalidasi terhadap schema draft Contracts.
- `FactoryExecutionContext` dan `AuthorityContext` milik Factory tetap terpisah dari
  `ExecutionContextView` dan `AuthorityContext` milik runtime. Kelompok pertama memproyeksikan
  request Factory canonical, sedangkan kelompok kedua merepresentasikan fakta eksekusi runtime
  yang telah dipersempit.
- `ToolBoundaryContracts` dipertahankan sebagai facade khusus karena boundary tool Backend
  memiliki kumpulan schema mandiri dan tanggung jawab validasi fail-closed.

## Penghapusan

- `AgentDraft` internal yang duplikat, `WorkforceControlPlane` yang usang, dan scaffold
  assessment terkait.
- Scaffold protocol `AgentRunInput`, `AgentRunResult`, dan `AgentRuntime`, beserta wrapper
  PydanticAI yang tidak digunakan dan bergantung kepadanya.
- `ExecutionPlan`, `RuntimePlanner`, dan `SinglePassPlanner` satu lintasan, serta cabang
  kompatibilitas yang tercampur di runtime inti.
- Helper kompatibilitas `FindingRecommendationBuilder.build()` yang tidak digunakan.
- Pohon package kosong untuk lifecycle, supervision, remediation, sustainability, taxonomy
  evaluasi, learning/consolidation memory, planning, synthesis, placeholder domain riset,
  disiplin review, dan recovery runtime yang belum diimplementasikan.

## Penggantian nama

- `AgentDraft` (proyeksi Factory) menjadi `AgentDraftProposal`.
- `EvaluationOutcome` milik Skill menjadi `SkillEvaluationOutcome`.
- `H7_DEFAULT_MODEL_TOKEN_BUDGET` menjadi `DEFAULT_RESEARCH_MODEL_TOKEN_BUDGET`.
- `MVP2_H8_REGRESSION_SET` menjadi `CORE_AI_ASSURANCE_REGRESSION_SET`.
- ID regresi `mvp2-h8-rc1-ai-regression` menjadi `core-ai-assurance-regression`.
- Field provenance regresi `created_from_milestone` menjadi `provenance_label`, dengan nilai
  `core-ai-feature-freeze`.
- Kebijakan riset dan identifier kasus assurance dipindahkan ke namespace semantik permanen.

## Kompatibilitas yang dipertahankan dan proyeksi yang disengaja

Tidak ada alias kompatibilitas source bernama tonggak yang dipertahankan. Versi proposal
regresi tetap `1.0.0` karena predicate, urutan, severity, dan perilakunya tidak berubah; hanya
kosakata identitas permanennya yang berubah. `CapabilityDefinition`, `AgentBlueprint`, model
dan protocol review, serta model perencanaan evaluasi dipertahankan karena semuanya merupakan
abstraksi domain aktif dan teruji, bukan duplikasi model canonical.

`ResearchEngine` tetap menjadi facade aplikasi canonical dari request ke result.
`ResearchOrchestrator` tetap menjadi pipeline internal untuk evidence, claim, conflict,
finding, dan recommendation. `BackendToolClient` tetap menjadi jalur HTTP yang benar menuju
Backend authoritative.

## Struktur assurance dan package

Probe assurance dipisahkan menjadi modul context, skill, memory, runtime, delegation, dan
research, dengan registry deterministik dan modul ekspor yang kecil. Pengujian kebersihan
berbasis AST mencegah identifier tonggak, definisi Agent draft duplikat, dan tipe planner satu
lintasan kembali ke source permanen.

## Catatan serah terima H9

H9 dapat mengintegrasikan field canonical atau adapter tambahan hanya melalui boundary
tervalidasi yang sudah ada. Ketidaksesuaian kontrak yang ditemukan kemudian harus ditangani
melalui perubahan Contracts terpisah. Pembersihan ini tidak mengubah `alos-contracts`, Backend,
frontend, infrastructure, status rilis, atau kewenangan approval.

## Bukti bahwa perilaku tetap terjaga

Pembersihan ini mempertahankan seluruh predicate deterministik, budget, urutan kasus,
pemeriksaan evidence dan subset kewenangan, validasi canonical, perilaku kegagalan aman, serta
boundary Backend/ModelGateway. Buktinya adalah rangkaian regresi perilaku yang tidak berubah,
Ruff, mypy, seluruh pytest, pemeriksaan impor aplikasi, dan workflow GitHub
`Kualitas GENESIS` pada `development` yang seluruhnya berhasil.
