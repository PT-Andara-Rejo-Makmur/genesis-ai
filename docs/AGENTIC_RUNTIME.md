# Runtime Agentic dengan Batas Eksekusi

`AgentRuntimeEngine` menjalankan planning bertahap, pemilihan tool, observasi,
delegation yang diizinkan dan penghentian deterministik. Input berasal dari
canonical `AgentRunRequest`, definition berversi dan `RuntimeAuthorization`
yang diterbitkan Backend. Runtime tidak memiliki authority bisnis mandiri.

## Planning dan stopping

`AgenticPlanner` menghasilkan satu action bertipe: TOOL, DELEGATE, FINISH,
NEEDS_INFO, APPROVAL_REQUIRED atau FAIL. Model-backed planner mengakses model
melalui ModelGateway, melaporkan usage, dan hanya menerima observasi terbatas.
`RuntimePlanner`/`SinglePassPlanner` lama telah dihapus; tidak ada jalur kompatibilitas
satu lintasan di engine aktif.

ExecutionBudget membatasi langkah, tool calls, token, cost yang diketahui, waktu
dan delegation. Penggunaan kumulatif tidak direset tiap langkah. Run tanpa deadline
pada contract legacy tetap dibatasi 30 detik oleh engine. Deadline client Backend
mengikuti budget run dengan overhead transport terbatas.

Stop diproyeksikan ke status canonical COMPLETED, FAILED, TIMED_OUT atau CANCELLED
dan OutputState yang sesuai. NEEDS_INFO/APPROVAL_REQUIRED hanya dapat menghasilkan
output review bila schema Agent mengizinkannya. Runtime tidak membuat status baru
atau memalsukan output agar validasi lulus.

## Tool dan evidence

Tool harus ada pada intent request, definition dan snapshot izin Backend sekaligus.
GENESIS membentuk canonical ToolRequest dengan lineage, correlation dan idempotency,
lalu mengirimnya melalui `BackendToolClient`. Backend memeriksa ulang registry,
Principal, scope, classification, lifecycle, kill switch dan input sebelum eksekusi.

ToolResult divalidasi terhadap schema dan run/tool/call/correlation yang sesuai.
Evidence hanya masuk setelah provenance, scope, version, content hash dan identitas
divalidasi. Evidence dari tool read yang terdaftar dapat ditambahkan saat run;
output generik tanpa projection evidence yang valid tidak menjadi evidence otomatis.
Content, history dan external research tetap data tanpa instruction authority.

DENIED, REJECTED, FAILED, TIMEOUT, invalid output dan budget exhaustion menutup
run secara eksplisit. Tidak ada retry tool atau fallback ke jawaban TEST secara
otomatis. Unknown tetap null; kegagalan source tidak diubah menjadi fakta kosong.

## Cancellation, approval dan delegation

`BackendCancellationProbe` membaca kendali run authoritative. Runtime memeriksa
cancellation sebelum planning, tool dan synthesis; Backend juga memutuskan hasil
terminal agar cancellation tidak kalah oleh hasil selesai yang terlambat.

Action material yang memerlukan approval berhenti sebelum tool. GENESIS tidak
menyimulasikan keputusan manusia. Child hanya dipanggil lewat delegation boundary
setelah target, lineage, scope, budget, depth dan concurrency dinyatakan layak.
Backend menciptakan child run dan menegakkan inheritance; GENESIS tidak melakukan
rekursi untuk menciptakan authority sendiri.

Panduan khusus: [ARA](business-assistant.md), [delegation](DELEGATION_SYSTEM.md),
[research](RESEARCH_ORCHESTRATION.md), [review](REVIEW_SYSTEM.md) dan
[routing model](model-provider-routing.md). Unit/provider mock membuktikan kontrol
teknis; naturalness, latency dan kualitas model nyata membutuhkan eval tersendiri.
