# Batas Otoritas

ALOS Backend memiliki authentication, RBAC, tenant authority, business state, ToolExecutor, audit authoritative, approval, dan release. GENESIS menerima execution context yang telah dibentuk Backend, tetapi tetap menerapkan limit dan tidak memperluasnya.

GENESIS menghasilkan ToolRequest, AIReviewResult, finding, recommendation, draft, dan backlog candidate. Artefak tersebut tidak mengeksekusi business action atau menjadi approval.

Provider adapter berada di belakang ModelGateway. Connector MCP berada di belakang tool boundary. PostgreSQL/pgvector target GENESIS hanya menyimpan runtime/reference/memory intelligence dan tidak menjadi business database.
