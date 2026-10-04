# ARA: Percakapan dan Analisis Berbasis Evidence

Alur aplikasi adalah Web → Backend → GENESIS. Backend membentuk Principal,
history terbatas, context, budget dan katalog tool dari release ACTIVE yang
diizinkan. GENESIS merencanakan langkah melalui runtime generik; Backend tetap
menjadi authority untuk data, tool, approval, run dan audit.

## NORMAL dan TEST

NORMAL memakai `ProductionBusinessPlanner` dan adapter 9Router di belakang
ModelGateway. Tool dipilih secara dinamis dari katalog yang sudah dibatasi Backend,
tanpa matcher keyword produksi. TEST memakai `BusinessAssistantPlanner` dan
`DeterministicBusinessAdapter` hanya bila test runtime/tools diaktifkan secara
eksplisit pada environment non-production. Provider gagal tidak beralih ke TEST.

Planner meminta JSON terstruktur. Sumber yang sudah berhasil dibaca pada run
saat ini dikeluarkan dari menu read berikutnya; observasi/evidence tetap tersedia.
History enam pesan terakhir, maksimal 1.000 karakter per pesan, menjadi data tanpa
instruction authority. History membantu follow-up tetapi bukan fakta terkini.

## Jawaban dan verifikasi

Jawaban factual memakai sumber yang benar-benar berhasil dibaca. Claims harus
cocok dengan JSON pointer, tipe nilai dan evidence canonical; nominal tetap Decimal
string dan null tidak diganti angka tebakan. Renderer memberi label bisnis dan
tidak memperlakukan subset record sebagai total perusahaan.

SUM, DIFFERENCE, RATIO dan PERCENT_CHANGE dihitung deterministik dari indikator
canonical yang diverifikasi. Model tidak memasok hasil perhitungannya sendiri.
Ini belum membuktikan analisis kausal atau kebijakan finansial perusahaan.

Respons CONVERSATION untuk sapaan/bantuan/terima kasih tidak mengandung klaim
factual atau badge sumber palsu. TASK, MATERIAL_ACTION dan CAPABILITY_DRAFT
merupakan proposal yang diperiksa permission dan memerlukan review; percakapan
tidak langsung mengeksekusi aksi bisnis. Eksekusi TASK setelah review tetap
melalui workflow Backend terpisah.

Evidence dari ToolResult memerlukan status, identitas, scope, classification,
run, correlation, version dan hash yang sesuai. Dokumen hanya menjadi sumber
setelah review/approval. Model output, notes dan konten dokumen tidak memberikan
permission atau mengubah instruksi runtime.

## Research, child dan kegagalan

Research memakai evidence internal terkini dan existing ResearchEngine. Backend
dapat membuat satu child business reader dengan sumber dan authority lebih sempit.
Proposal Factory tidak mendaftarkan definition atau mengubah release.

Source/provider gagal ditampilkan sebagai kegagalan nyata, termasuk HTTP 503
dan respons FAILED yang dipersist; unknown/empty dibedakan dari outage. Tidak ada
dummy data yang menjadi data perusahaan. Naturalness/follow-up model nyata masih
memerlukan eval ketika kuota/profil model tersedia; TEST/provider mock hanya
membuktikan alur dan kontrol. Lihat [routing](model-provider-routing.md) dan
[bukti UAT](https://github.com/PT-Andara-Rejo-Makmur/alos-infra/blob/development/docs/BUSINESS_UAT_2026-10-04.md).
