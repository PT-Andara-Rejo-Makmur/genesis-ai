# Peran MCP

MCP menyediakan interoperability connector dan tool metadata. MCP tidak memberikan authority baru kepada GENESIS atau Agent.

Adapter MCP hanya menyiapkan connector metadata dan argument untuk ToolRequest. Aksi bisnis tetap melewati ALOS Backend ToolExecutor, yang memvalidasi tenant, scope, permission, allowlist, dan audit. MCP tidak boleh menjadi direct business execution path.
