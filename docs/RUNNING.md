# Menjalankan Service

Setelah virtual environment aktif dan dependency terpasang:

```bash
uvicorn genesis.main:app --reload --host 127.0.0.1 --port 8100
```

Periksa `/health`, `/ready`, `/internal/v1/system/info`, `/internal/v1/system/integration`, dan `/docs`. Endpoint internal memerlukan `Authorization: Bearer <ALOS_INTERNAL_TOKEN>` ketika token dikonfigurasi. Token kosong hanya ditoleransi pada environment development/test. Endpoint integration hanya membuktikan boundary internal dan meneruskan `X-Correlation-ID`; endpoint tersebut tidak memakai provider atau business database. Health/readiness juga tidak memerlukan provider credential. `DEFAULT_MODEL_ROUTE=disabled` memastikan tidak ada accidental provider call.

Environment utama tersedia di `.env.example`. `ALOS_INTERNAL_TOKEN` merupakan secret dan harus diberikan melalui secret manager deployment pada staging/production.
