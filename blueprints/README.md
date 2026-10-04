# Blueprint GENESIS

Blueprint adalah template deklaratif tanpa registry, permission atau approval
authority. Definition yang dijalankan berasal dari versi registry Backend yang
telah disahkan, bukan dari penamaan folder.

`skills/research/` berisi `skill.yaml` dan `SKILL.md` untuk core, technology,
management, property_business dan property_market. Loader hanya membaca metadata
saat discovery, lalu memuat instruksi ketika relevan. Instruksi tidak memberi
izin HTTP, tool, akses database atau keputusan manusia.

Folder placeholder Agent/workflow/evaluator/domain-profile diringkas ke panduan
ini karena belum memiliki template executable. Lihat
[Skill System](../docs/SKILL_SYSTEM.md) dan [Agent architecture](../docs/AGENT_ARCHITECTURE.md).
