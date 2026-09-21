# Riset Teknologi

## 1. Tujuan dan ruang lingkup

Gunakan Skill ini untuk mengevaluasi model AI, framework, library, platform, tool, dependency, pola
arsitektur, atau pilihan teknologi lain. Tujuannya adalah menghasilkan perbandingan berbasis bukti
dan rekomendasi draft, bukan memilih vendor secara otomatis atau mengubah sistem produksi.

Skill ini menggunakan prosedur **Riset Berbasis Bukti** dan domain `TECHNOLOGY` pada taxonomy yang
sudah ada. `ResearchEngine`, evidence model, context semantics, dan tool boundary tetap sama.

## 2. Input minimum

Pastikan tersedia:

- problem statement dan outcome bisnis/teknis;
- use case, user, workload, volume, latency, availability, dan data classification;
- lingkungan target, arsitektur saat ini, integration points, dan constraint migrasi;
- security, compliance, deployment, observability, dan support requirement;
- horizon waktu dan batas biaya;
- alternatif yang harus dibandingkan atau aturan pembentukan shortlist;
- evidence versi dan tanggal yang relevan.

Jika requirement belum cukup untuk membedakan alternatif, kembalikan `NEEDS_INFORMATION`.

## 3. Prosedur domain

### 3.1 Bentuk baseline kebutuhan

Kelompokkan requirement menjadi:

- functional capability;
- performance dan scalability;
- security dan privacy;
- interoperability dan portability;
- reliability dan operability;
- developer experience dan maintainability;
- licensing, support, cost, dan vendor risk;
- migration effort serta reversibility.

Tandai requirement sebagai wajib, diinginkan, atau opsional. Jangan mengubah preference menjadi
requirement tanpa dasar.

### 3.2 Susun alternatif dan versi

Untuk setiap alternatif, catat nama produk/proyek, versi, edition, deployment model, license, status
support, tanggal rilis, dan asumsi konfigurasi. Jangan membandingkan versi yang berbeda seolah-olah
memiliki capability atau risk profile yang sama.

### 3.3 Gunakan matriks evaluasi konsisten

| Dimensi | Pemeriksaan minimum |
|---|---|
| Fitness | Coverage use case, batas fitur, extensibility, dan kesesuaian arsitektur |
| Security | AuthN/AuthZ, isolasi, secret, encryption, advisory, patching, dan supply chain |
| Interoperability | API, protocol, data format, integration, portability, dan vendor lock-in |
| Performance | Workload, latency, throughput, concurrency, resource use, dan kondisi benchmark |
| Reliability | Failure mode, retry, recovery, consistency, HA, backup, dan disaster recovery |
| Operability | Deployment, observability, auditability, upgrade, rollback, dan incident response |
| Maintainability | Complexity, testability, dokumentasi, ecosystem, release cadence, dan talent |
| Cost | License, compute, storage, network, implementation, migration, operation, dan exit cost |
| Maturity | Production adoption, roadmap, governance proyek, support, dan end-of-life risk |

Jelaskan weighting jika digunakan. Jangan menghasilkan skor total yang menyembunyikan kegagalan
pada requirement wajib.

### 3.4 Nilai evidence

Prioritaskan:

1. standard dan dokumentasi resmi berversi;
2. release note, security advisory, compatibility matrix, dan license resmi;
3. benchmark reproducible dengan dataset dan konfigurasi yang dijelaskan;
4. bukti internal terotorisasi dari workload yang sebanding;
5. laporan independen dengan metode transparan;
6. vendor marketing atau opini komunitas hanya sebagai evidence pendukung ber-confidence rendah.

Untuk benchmark, catat hardware, software version, konfigurasi, dataset, ukuran sample, warm-up,
concurrency, metric definition, sponsor, dan tanggal. Jangan membandingkan angka dengan metode atau
workload berbeda tanpa normalisasi dan limitation.

### 3.5 Analisis risiko dan trade-off

Untuk setiap alternatif, jelaskan:

- requirement wajib yang dipenuhi atau gagal;
- benefit utama dan biaya tersembunyi;
- security dan compliance gap;
- integration dan migration risk;
- lock-in dan exit strategy;
- operational burden;
- unknown yang membutuhkan proof of concept.

### 3.6 Bentuk rekomendasi

Rekomendasi harus memilih salah satu bentuk:

- lanjutkan desk evaluation;
- lakukan proof of concept terbatas;
- lakukan security/architecture review;
- pertahankan teknologi saat ini;
- tunda karena evidence tidak cukup;
- rekomendasikan adopsi atau penolakan untuk human approval.

Jika proof of concept disarankan, definisikan hypothesis, dataset, environment, success metric,
timebox, owner, risk control, dan exit criteria. Jangan menjalankan PoC dari Skill ini.

## 4. Penanganan konflik

- Utamakan evidence untuk versi dan deployment model yang benar.
- Bedakan hasil lab, vendor benchmark, dan workload produksi.
- Jika vendor claim berbeda dengan benchmark independen, tampilkan keduanya beserta metode dan bias.
- Jika advisory keamanan belum memiliki remediation, tandai residual risk dan minta Security review.
- Jika biaya tidak memiliki basis volume yang sebanding, jangan menyatakan alternatif lebih murah.

## 5. Format keluaran domain

1. Kebutuhan dan constraint.
2. Alternatif serta versi yang dibandingkan.
3. Matriks kriteria dan evidence per alternatif.
4. Requirement wajib yang gagal.
5. Security, integration, migration, operational, dan cost risk.
6. Konflik evidence dan unknown.
7. Rekomendasi draft serta reviewer yang diperlukan.
8. Rencana validasi/PoC jika diperlukan.

## 6. Larangan tindakan otomatis

Jangan menginstal dependency, menjalankan binary, memodifikasi repository, mengubah ModelGateway,
mengganti provider, mengubah infrastructure, credential, security policy, deployment, atau production
configuration. Semua perubahan teknis memerlukan workflow, review, dan approval terpisah.

## 7. Checklist evaluasi

- [ ] Requirement wajib dan constraint telah ditetapkan.
- [ ] Versi, edition, license, dan deployment model setiap alternatif jelas.
- [ ] Semua alternatif dibandingkan dengan kriteria yang sama.
- [ ] Klaim security, compatibility, performance, dan biaya memiliki evidence.
- [ ] Metode benchmark dan keterbatasannya dijelaskan.
- [ ] Lock-in, migration, operation, dan exit cost dibahas.
- [ ] Unknown menghasilkan validation plan, bukan asumsi tersembunyi.
- [ ] Rekomendasi tidak melakukan perubahan teknis otomatis.
