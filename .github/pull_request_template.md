## Ringkasan

Jelaskan perubahan capability, runtime, orchestration, atau adapter.

## Pemeriksaan authority dan arsitektur

- [ ] GENESIS tetap bukan business/approval/release authority.
- [ ] Tidak ada direct provider call dari domain Agent.
- [ ] Framework hanya digunakan melalui `adapters/`.
- [ ] Aksi bisnis tetap menghasilkan ToolRequest untuk ALOS Backend.
- [ ] Delegation tidak memperluas permission, scope, tool, atau budget.
- [ ] Schema `alos-contracts` tidak diduplikasi.

## Validasi

- [ ] Ruff lulus
- [ ] mypy lulus
- [ ] pytest dan architecture checks lulus
- [ ] Tidak ada secret atau provider key
