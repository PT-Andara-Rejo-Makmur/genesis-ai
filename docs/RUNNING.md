# Menjalankan Service

Setelah virtual environment aktif dan dependency terpasang:

```bash
uvicorn genesis.main:app --reload --host 127.0.0.1 --port 8100
```

Periksa `/health`, `/ready`, `/internal/v1/system/info`, dan `/docs`. Health/readiness tidak memerlukan provider credential. `DEFAULT_MODEL_ROUTE=disabled` memastikan tidak ada accidental provider call.

Environment utama tersedia di `.env.example`. `ALOS_INTERNAL_TOKEN` merupakan secret dan harus diberikan melalui secret manager deployment pada staging/production.
