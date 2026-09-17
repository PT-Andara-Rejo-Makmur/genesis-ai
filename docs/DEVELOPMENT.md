# Pengembangan

Domain harus framework-agnostic. Definisikan model dan Protocol pada package domain, kemudian implementasikan PydanticAI, LangGraph, MCP, atau provider di `src/genesis/adapters/`.

Aturan perubahan:

- Capability-first sebelum Agent-first.
- Satu generic runtime untuk seluruh logical Agent.
- Satu MCA untuk business orchestration.
- Model access hanya melalui ModelGateway.
- Business action hanya melalui ToolRequest ke ALOS Backend.
- Dynamic Agent dan Skill hanya menghasilkan draft.
- Delegation wajib mempertahankan lineage dan tidak memperluas authority.
- Gunakan schema/release `alos-contracts`, bukan salinan lokal.

Quality gate:

```bash
ruff check .
mypy
pytest
```
