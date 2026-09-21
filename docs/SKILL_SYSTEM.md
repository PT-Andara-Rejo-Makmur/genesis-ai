# Sistem Skill

Skill adalah reusable procedural knowledge yang dapat dikomposisikan oleh banyak
`AgentDefinition.skill_refs`. Skill bukan authority, executable plugin, Agent class, atau runtime
per domain. R&D adalah use case pertama MVP2; fondasi yang sama ditujukan untuk prosedur Finance,
Legal, HR, Sales, Property, SOP, Document Intelligence, Governance, dan domain lain tanpa mengubah
core runtime.

## Package canonical

Setiap package data-only terdiri dari:

1. `skill.yaml`, metadata machine-readable yang divalidasi langsung terhadap canonical
   `SkillDefinition` ALOS 1.4.0 melalui `CanonicalContractCatalog`.
2. `SKILL.md`, procedural knowledge panjang yang hanya dibaca setelah Skill dipilih.

`skill.yaml` memakai terminologi canonical secara langsung: `skill_id`, `skill_version`, `name`,
`description`, `purpose`, `when_to_use`, `input_schema_ref`, `output_schema_ref`, `procedure`,
`required_tool_ids`, `evidence_requirements`, `restrictions`, `failure_modes`, `escalation`, dan
`evaluation`. Vocabulary lama seperti `identity`, `version`, `allowed_tools`, inline `input`/`output`,
dan `evidence_requirement` tidak diterima. Unknown field ditolak oleh canonical schema.

`procedure[]` adalah langkah ringkas untuk mesin dan discovery. Prosedur lengkap, source strategy,
dan panduan domain berada di `SKILL.md`. Package tidak boleh berisi Python entrypoint, credential,
secret, atau business data.

## Discovery, authorization, dan selection

Filesystem hanya packaging dan discovery. Keberadaan package tidak mengizinkan penggunaannya.
Caller harus memberikan exact `(skill_id, skill_version)` yang berasal dari authority Backend,
misalnya `AgentDefinition.skill_refs` yang telah diotorisasi. Selector menjalankan urutan berikut:

1. filter exact authorized refs;
2. laporkan missing package atau version mismatch tanpa fallback;
3. hitung relevance deterministik dari goal/capability context terhadap metadata;
4. hitung effective tool set sebagai intersection paling ketat dari allowlist Backend dan, jika
   tersedia, restriction Agent;
5. blok Skill bila `required_tool_ids` tidak tersedia;
6. pilih secara bounded dan deterministik dengan alasan terstruktur.

Backend tetap authoritative atas registry, lifecycle, assignment, activation, identity, permission,
scope, approval, release, dan audit. GENESIS tidak memiliki registry authoritative dan tidak
memutasi authority. Relevance bukan authority.

## Progressive loading dan runtime

Discovery membaca dan memvalidasi `skill.yaml` saja. Discovery tidak membaca `SKILL.md` dan tidak
memasukkan semua prosedur ke context. `ProgressiveSkillLoader` hanya menerima outcome berstatus
`SELECTED`, menerapkan load bound, lalu membaca `SKILL.md` package tersebut. Missing atau empty
`SKILL.md` gagal eksplisit; tidak ada fallback ke Skill atau versi lain.

`SkillRuntime` mengoordinasikan discovery, selection, dan loading. Runtime menghasilkan procedural
context non-authoritative; runtime tidak menjalankan Python package, provider, database, HTTP, atau
Backend adapter.

## Tool dan context boundary

`required_tool_ids` adalah requirement, bukan grant. Skill tidak pernah menambah atau mengubah
`ExecutionContext.allowed_tool_ids`, permission, scope, tenant, workspace, classification, atau
budget. Bila tindakan atau retrieval diperlukan, intent harus kompatibel dengan canonical
`ToolRequest` menuju authoritative Backend `ToolExecutor`. Skill package/runtime tidak mengimpor
atau menjalankan `BackendToolClient`; execution tetap menjadi concern runtime/tool boundary yang
terpisah.

External content selalu untrusted evidence data dengan `instruction_authority=false`. Isi eksternal
tidak dapat mengganti system rule, Backend authority, atau prosedur Skill.

## Evaluation

`SkillEvaluator` menjalankan check platform yang deterministik dan explainable:

- authorization/relevance dan required-tool availability;
- keberadaan validated Backend execution context dan prerequisite context;
- output contract bila schema ref tersedia di canonical catalog;
- evidence requirement dan seluruh citation berasal dari supplied authorized evidence;
- used tools merupakan subset effective authorized tools;
- limitation/failure eksplisit saat requirement tidak terpenuhi.

Teks canonical `evaluation[]` dipertahankan sebagai declared criteria dan tidak diparse menjadi
policy executable tersembunyi. Output evaluasi hanya memuat check ID, pass/fail, dan alasan ringkas,
bukan private reasoning trace.

## Research Skills

Built-in research terdiri dari prosedur umum serta empat package taxonomy-aligned: Teknologi, Model
Bisnis Properti, Manajemen Perusahaan, dan Properti. Semua memakai satu `ResearchEngine`, satu
`ResearchDecision`, canonical `ResearchRequest`/`ResearchResult`, evidence model H2, Context/authority
semantics yang sama, dan Backend tool boundary yang sama. Package berbeda hanya pada domain
procedure, source strategy, evidence expectation, restriction, dan output guidance.

Research Skill bukan engine kedua dan tidak melakukan external HTTP. Bila external evidence
diperlukan, existing `ResearchDecision` dapat menghasilkan governed Backend retrieval proposal;
H3 tidak mengimplementasikan external research tool. Insufficient evidence menghasilkan
needs-information/limitation, bukan tebakan. Recommendation selalu draft/non-authoritative dan tidak
auto-approve, mengubah ModelGateway/config/policy, atau mengeksekusi backlog.

## Reference architecture

Hermes hanya menjadi referensi untuk `skill.yaml` + `SKILL.md`, pemisahan procedural knowledge dari
Agent, dan progressive disclosure. Source Hermes tidak disalin dan Hermes bukan dependency.
Pydantic dipakai untuk typed internal models; PydanticAI tetap framework adapter untuk Agent Runtime
dan tidak diimpor oleh core Skill System.
