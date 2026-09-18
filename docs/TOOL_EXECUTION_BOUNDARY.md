# Boundary Eksekusi Tool

GENESIS tidak menjalankan business tool. Runtime hanya menggunakan `BackendToolClient` untuk flow:

```text
GENESIS → ToolRequest → ALOS Backend ToolExecutor → ToolResult → GENESIS
```

`ToolBoundaryContracts` memvalidasi request dan result menggunakan schema dari `alos-contracts`.
Client meneruskan service token dan `X-Correlation-ID`, lalu menolak result yang tidak valid atau
memiliki correlation ID berbeda.

GENESIS bertanggung jawab atas penyusunan request dan penggunaan result untuk reasoning berikutnya.
Backend tetap bertanggung jawab atas identity resolution, authorization, tenant/scope/permission
policy, allowlist, adapter execution, timeout, audit, dan structured outcome.

Helper `diagnostic_echo_request` hanya menghasilkan data contract untuk integration test. Helper
tersebut bukan adapter dan tidak mengeksekusi tool. Tidak ada business database atau provider yang
digunakan dalam flow ini.
