"""Professional business prose rendered exclusively from verified canonical values."""

from typing import Any

from genesis.runtime.assistant.sources import data_only

SOURCE_LABELS = {
    "executive.overview.read": "Kondisi perusahaan",
    "strategy.plan.read": "Rencana strategis",
    "strategy.target.read": "Target dan kinerja",
    "shared.project.list": "Proyek",
    "shared.project.read": "Rincian proyek",
    "shared.task.list": "Tugas",
    "shared.task.read": "Rincian tugas",
    "shared.approval.list": "Pengajuan persetujuan",
    "shared.document.read": "Dokumen pendukung",
    "document.content.read": "Isi dokumen",
    "shared.finding.list": "Temuan",
    "shared.report.read": "Laporan",
    "sales.overview.read": "Penjualan",
    "sales.summary.read": "Kinerja penjualan",
    "sales.lead.list": "Calon pelanggan",
    "sales.opportunity.list": "Peluang penjualan",
    "sales.booking.read": "Pemesanan",
    "process.queue.read": "Pengajuan dan langkah berikutnya",
    "process.detail.read": "Rincian pengajuan",
    "marketing.overview.read": "Pemasaran",
    "marketing.campaign.list": "Kampanye pemasaran",
    "property.overview.read": "Properti",
    "property.unit.list": "Unit properti",
    "property.progress.read": "Kemajuan pembangunan",
    "finance.overview.read": "Keuangan",
    "finance.receivable.list": "Piutang",
    "finance.payable.list": "Utang",
    "finance.budget.read": "Anggaran",
    "hr.overview.read": "SDM dan umum",
    "hr.employee.summary": "Karyawan",
    "hr.recruitment.summary": "Rekrutmen",
    "legal.overview.read": "Legal",
    "legal.risk.list": "Risiko legal",
    "legal.contract.read": "Kontrak",
    "it.overview.read": "Teknologi informasi",
    "it.incident.list": "Insiden TI",
    "it.system.list": "Sistem TI",
}

_LABELS = {
    "name": "Nama",
    "title": "Judul",
    "status": "Status",
    "amount": "Nilai",
    "description": "Keterangan",
    "summary": "Ringkasan",
    "due_date": "Jatuh tempo",
    "priority": "Prioritas",
    "severity": "Tingkat dampak",
    "progress": "Kemajuan",
    "leads": "Calon pelanggan",
    "opportunities": "Peluang penjualan",
    "bookings": "Pemesanan",
    "projects": "Proyek",
    "tasks": "Tugas",
    "receivables": "Piutang",
    "payables": "Utang",
    "employees": "Karyawan",
    "contracts": "Kontrak",
    "incidents": "Insiden TI",
    "systems": "Sistem TI",
    "budgets": "Anggaran",
    "campaigns": "Kampanye",
    "risks": "Risiko",
    "total": "Jumlah",
    "count": "Jumlah catatan",
    "counts": "Jumlah catatan",
    "total_amount": "Nilai total",
    "outstanding_amount": "Nilai belum terselesaikan",
    "paid_amount": "Nilai telah dibayar",
    "balance": "Saldo",
    "currency": "Mata uang",
    "source_status": "Ketersediaan sumber",
    "source_state": "Ketersediaan sumber",
    "period": "Periode",
    "metrics": "Indikator",
    "resources": "Catatan operasional",
    "domains": "Divisi",
    "domain": "Divisi",
    "message": "Keterangan sumber",
    "shared_work": "Pekerjaan bersama",
    "strategy": "Strategi",
}
_STATUS = {
    "UNAVAILABLE": "Belum tersedia",
    "NOT_CONNECTED": "Belum terhubung",
    "FAILED": "Gagal dibaca",
    "ACTIVE": "Aktif",
    "INACTIVE": "Tidak aktif",
    "PENDING": "Menunggu",
    "DRAFT": "Draf",
    "COMPLETED": "Selesai",
    "CANCELLED": "Dibatalkan",
    "APPROVED": "Disetujui",
    "REJECTED": "Ditolak",
    "OPEN": "Terbuka",
    "CLOSED": "Ditutup",
    "OVERDUE": "Lewat jatuh tempo",
}
_HIDDEN = {"captured_at", "content_hash", "uri", "tool_id", "correlation_id"}


def _label(key: str) -> str:
    return _LABELS.get(key, key.replace("_", " ").capitalize())


def _scalar(value: Any) -> str:
    if value is None:
        return "belum tersedia"
    if isinstance(value, bool):
        return "Ya" if value else "Tidak"
    return _STATUS.get(str(value), str(value))


def _lines(value: Any, *, depth: int = 0) -> list[str]:
    if depth >= 5:
        return ["Rincian lebih lanjut tersedia pada sumber pendukung."]
    if isinstance(value, dict):
        if (
            isinstance(value.get("label"), str)
            and "code" in value
            and "source" in value
            and type(value.get("available")) is bool
            and "value" in value
            and value.get("unit") in ("COUNT", "AMOUNT", "PERCENT")
        ):
            label = value["label"]
            if not value["available"] or value["value"] is None:
                return [f"{label}: belum tersedia."]
            prefix = "Rp " if value["unit"] == "AMOUNT" else ""
            suffix = "%" if value["unit"] == "PERCENT" else ""
            return [f"{label}: {prefix}{_scalar(value['value'])}{suffix}."]
        lines = []
        for key, item in data_only(value).items():
            if key in _HIDDEN or key.endswith(("_id", "_ref", "_refs")):
                continue
            if isinstance(item, dict | list):
                lines.append(_label(key) + ":")
                lines.extend(_lines(item, depth=depth + 1))
            else:
                lines.append(f"{_label(key)}: {_scalar(item)}.")
        return lines or ["Rincian bisnis belum tersedia pada catatan ini."]
    if isinstance(value, list):
        if not value:
            return ["Tidak ada catatan pada hasil pembacaan ini."]
        lines = [f"Hasil pembacaan memuat {len(value)} catatan."]
        for index, item in enumerate(value[:5], start=1):
            lines.append(f"{index}. " + " ".join(_lines(item, depth=depth + 1)))
        if len(value) > 5:
            lines.append("Lima catatan ditampilkan; buka sumber untuk rincian lainnya.")
        return lines
    return [_scalar(value) + "."]


def present_claim(tool_id: str, pointer: str, value: Any) -> str:
    title = SOURCE_LABELS.get(tool_id, "Informasi perusahaan")
    if pointer != "/data":
        field = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
        if not field.isdecimal():
            title += " — " + _label(field)
    return title + "\n" + "\n".join(_lines(value))
