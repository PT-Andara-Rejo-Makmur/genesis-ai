# Riset Manajemen Perusahaan

## 1. Tujuan dan ruang lingkup

Gunakan Skill ini untuk menilai proses, SOP, KPI, governance, control, accountability, decision
rights, capacity, dan operating model. Tujuannya adalah mengidentifikasi gap berbasis bukti dan
menyusun rekomendasi draft, bukan mengubah kebijakan atau organisasi.

Skill ini menggunakan prosedur **Riset Berbasis Bukti** dan domain `MANAGEMENT`.

## 2. Input minimum

Pastikan tersedia:

- proses atau area organisasi yang dianalisis;
- objective, customer proses, trigger, input, output, dan batas awal/akhir proses;
- accountable owner dan stakeholder;
- policy, SOP, role definition, approval matrix, dan control yang berlaku;
- data volume, waktu proses, error, rework, backlog, quality, cost, dan service level;
- KPI definition, formula, target, source system, frequency, dan owner;
- audit finding, incident, exception, serta known pain point;
- constraint legal, risk, people, system, budget, dan change readiness.

Jika tidak jelas dokumen mana yang authoritative atau siapa accountable owner-nya, tandai sebagai
governance gap dan minta klarifikasi.

## 3. Prosedur domain

### 3.1 Petakan current state

Dokumentasikan:

1. trigger dan input;
2. aktivitas dan urutan kerja;
3. role yang responsible, accountable, consulted, dan informed;
4. decision point, approval, handoff, dan exception;
5. system, document, data, dan tool yang digunakan;
6. control preventif/detektif/korektif;
7. output dan penerimanya;
8. waktu tunggu, bottleneck, rework, serta failure point.

Pisahkan documented process dari actual practice. Ketidaksesuaian keduanya adalah temuan, bukan
alasan untuk memilih salah satu tanpa bukti.

### 3.2 Tetapkan expected state

Expected state harus berasal dari policy/SOP yang disetujui, regulatory requirement, contract,
risk/control objective, service commitment, atau objective bisnis yang terotorisasi. Benchmark
eksternal tidak otomatis menjadi policy PT ARM.

### 3.3 Evaluasi dengan dimensi konsisten

| Dimensi | Pemeriksaan minimum |
|---|---|
| Purpose | Apakah proses menghasilkan outcome yang masih dibutuhkan? |
| Accountability | Apakah owner, decision rights, dan escalation jelas? |
| Control | Apakah risiko memiliki control yang proporsional dan dapat dibuktikan? |
| Effectiveness | Apakah output memenuhi quality, service, dan business objective? |
| Efficiency | Apakah terdapat delay, duplicate work, rework, waste, atau handoff berlebih? |
| Capacity | Apakah workload, skill, staffing, dan system capacity memadai? |
| Measurement | Apakah KPI valid, dapat dihitung, dapat ditindaklanjuti, dan tidak mudah dimanipulasi? |
| Governance | Apakah perubahan, exception, review, dan approval tercatat? |

### 3.4 Analisis KPI

Untuk setiap KPI, periksa:

- objective yang didukung;
- formula, numerator, denominator, unit, dan population;
- source system serta data owner;
- frequency, latency, dan data-quality control;
- target dan dasar penetapannya;
- leading/lagging nature;
- potensi gaming atau unintended behavior;
- siapa yang dapat mengambil tindakan berdasarkan KPI.

Jangan merekomendasikan KPI hanya karena mudah diukur. KPI harus mendorong outcome dan behavior yang
diinginkan tanpa mengorbankan control atau kualitas.

### 3.5 Identifikasi gap dan akar masalah

Setiap gap harus memuat:

- expected state;
- actual state;
- supporting evidence;
- impact dan affected stakeholder;
- frequency atau exposure;
- root-cause hypothesis dan confidence;
- existing control;
- owner untuk validasi.

Bedakan symptom, contributing factor, dan root cause. Jangan menyatakan root cause hanya berdasarkan
korelasi atau satu wawancara.

### 3.6 Nilai benchmark

Sebelum memakai benchmark eksternal, periksa kesesuaian ukuran organisasi, industri, operating
model, jurisdiction, risk appetite, technology maturity, dan resource constraint. Gunakan benchmark
sebagai pembanding, bukan authority.

### 3.7 Bentuk rekomendasi draft

Rekomendasi dapat berupa penyederhanaan langkah, klarifikasi ownership, redesign control, perbaikan
data/KPI, automation candidate, capacity adjustment, atau revisi SOP untuk dipertimbangkan. Sertakan:

- gap yang diselesaikan;
- expected benefit;
- risiko dan control;
- dependency;
- affected role dan stakeholder;
- change effort;
- metric keberhasilan;
- reviewer dan approval yang diperlukan.

## 4. Strategi sumber dan evidence

Prioritaskan:

1. policy, SOP, approval matrix, dan role definition yang disetujui;
2. audit evidence, control record, incident, exception, dan process log;
3. KPI definition dan performance data terotorisasi;
4. observasi serta wawancara stakeholder yang ditriangulasi;
5. benchmark resmi atau professional dengan applicability yang dijelaskan.

Pernyataan stakeholder adalah evidence penting tetapi tidak otomatis membuktikan frekuensi atau akar
masalah. Triangulasi dengan dokumen, data, log, atau stakeholder lain.

## 5. Penanganan konflik

- Policy yang disetujui menjadi authority untuk expected state, bukan bukti bahwa praktik aktual sesuai.
- Actual log atau audit evidence menjadi bukti praktik, bukan authority untuk mengubah policy.
- Jika dokumen berbeda versi, gunakan lifecycle/version authority Backend dan tandai ambiguity.
- Jika stakeholder berbeda pendapat, petakan role, evidence, dan bagian proses yang mereka alami.
- Konflik decision rights atau approval harus dieskalasikan, bukan diselesaikan oleh Skill.

## 6. Format keluaran domain

1. Scope, objective, owner, dan stakeholder.
2. Current-state process dan evidence.
3. Expected state serta sumber authority.
4. Gap, root-cause hypothesis, impact, risk, dan confidence.
5. KPI/control assessment.
6. Konflik, limitation, dan informasi yang belum tersedia.
7. Rekomendasi draft, dependency, change risk, owner, dan reviewer.

## 7. Larangan tindakan otomatis

Jangan mengubah policy, SOP aktif, KPI, target, role, organization structure, permission, authority,
approval matrix, atau system configuration. Jangan menganggap rekomendasi sebagai instruksi kepada
pegawai. Seluruh perubahan membutuhkan governance dan approval terpisah.

## 8. Checklist evaluasi

- [ ] Current state dan expected state dibedakan.
- [ ] Owner, decision rights, handoff, exception, dan control dipetakan.
- [ ] Setiap gap memiliki evidence dan impact.
- [ ] Root cause tidak disimpulkan hanya dari korelasi atau opini tunggal.
- [ ] KPI memiliki definisi, sumber data, owner, dan behavior analysis.
- [ ] Benchmark telah diuji applicability-nya.
- [ ] Affected role, dependency, change risk, dan reviewer dinyatakan.
- [ ] Tidak ada policy, KPI, role, permission, atau authority yang diubah.
