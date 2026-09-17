# Panduan Kontribusi

1. Pertahankan capability-first dan hindari membuat Agent ketika rule, validator, report, workflow, atau human task sudah cukup.
2. Tambahkan domain interface terlebih dahulu; framework implementation hanya berada di `adapters/`.
3. Jangan menambahkan provider SDK import ke Agent, Skill, orchestration, review, research, atau control-plane domain.
4. Jangan menyalin schema dari `alos-contracts`.
5. Jangan menambahkan direct business database access atau authoritative decision.
6. Tambahkan deterministic test serta taxonomy berbasis risiko.
7. Jalankan `ruff check .`, `mypy`, dan `pytest` sebelum pull request.

Perubahan yang memengaruhi authority, delegation, budget, ModelGateway, atau tool boundary harus dijelaskan secara eksplisit dalam pull request.
