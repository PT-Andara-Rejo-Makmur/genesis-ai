# ADR-004: Otoritas Tetap pada ALOS Backend

- Status: Diterima
- Tanggal: 2026-09-16

## Keputusan

GENESIS tidak memiliki business database, final approval, release, atau ToolExecutor authority. Aksi Agent menjadi ToolRequest ke ALOS Backend.

## Konsekuensi

AI review, research recommendation, AgentDraft, dan SkillDraft selalu non-authoritative sampai diproses oleh Backend.
