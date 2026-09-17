# ADR-002: Satu MCA

- Status: Diterima
- Tanggal: 2026-09-16

## Keputusan

MCA merupakan satu-satunya master business orchestrator. Control Plane mengelola workforce lifecycle dan tidak menjadi orchestrator kedua.

## Konsekuensi

Architecture test menolak penambahan class Coordinator kedua tanpa ADR pengganti.
