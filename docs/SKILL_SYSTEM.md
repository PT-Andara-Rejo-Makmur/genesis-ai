# Sistem Skill

ALOS Skill terdiri dari dua bagian:

1. `skill.yaml` berisi specification metadata yang dapat ditemukan tanpa memuat prosedur panjang.
2. `SKILL.md` berisi reusable procedural knowledge yang hanya dimuat ketika Skill relevan.

Specification minimal memuat `identity`, `version`, `purpose`, `when_to_use`, `input`, `output`, `procedure`, `allowed_tools`, `evidence_requirement`, `restrictions`, `failure_modes`, `escalation`, dan `evaluation`.

## Progressive loading

Discovery membaca metadata terlebih dahulu. Runtime memilih Skill berdasarkan purpose dan `when_to_use`, lalu loader membaca `SKILL.md`. Pola ini mengurangi context cost serta mencegah instruksi yang tidak relevan masuk ke run.

Skill bukan unrestricted code execution. Tool yang digunakan harus termasuk allowlist dan aksi bisnis tetap dikirim sebagai ToolRequest ke Backend.

Self-created Skill selalu menjadi SkillDraft. Learning dapat mengusulkan perbaikan, tetapi activation memerlukan review dan authority ALOS.
