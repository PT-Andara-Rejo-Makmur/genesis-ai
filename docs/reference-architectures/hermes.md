# Hermes sebagai Reference Architecture

Hermes digunakan sebagai referensi pola, bukan source code atau runtime dependency.

## Diadopsi

- Pola `SKILL.md` untuk procedural knowledge reusable.
- Progressive disclosure: temukan metadata, lalu muat instruksi penuh ketika relevan.
- Pemisahan knowledge procedural dari kode Agent.

## Diadaptasi

- Memory wajib tenant-scoped, memiliki provenance, retention, dan governance.
- Sub-agent delegation wajib memiliki lineage, limit, cycle prevention, dan authority inheritance.
- Self-created Skill hanya menghasilkan SkillDraft dan tidak dapat self-activate.
- MCP ditempatkan di belakang governed tool boundary.
- Self-improvement menjadi proposal/evaluation/remediation yang memerlukan review.

## Ditolak

- Unrestricted autonomy.
- Self-approval atau self-release.
- Bypass Backend ToolExecutor.
- Authority di luar ALOS Backend.
- Provider atau business database credential langsung pada Agent.

Tidak ada source Hermes yang disalin secara mentah.
