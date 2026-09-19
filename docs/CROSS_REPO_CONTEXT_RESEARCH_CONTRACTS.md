# Cross-Repository Context and Research Contracts

## `alos-contracts`

Canonical `ExecutionContext`, `ContextBundle`, `EvidenceRef`, `EvidenceBundle`, dan
`ResearchDecision` digunakan serta divalidasi langsung dari schema `alos-contracts`.
GENESIS mempertahankan typed runtime model internal, tetapi hanya mengirim projection
canonical lintas boundary. Ranking, trimming, domain profile, dan authorization snapshot
internal tidak menjadi bagian payload canonical.

## `alos-backend`

Backend harus tetap membentuk dan menandatangani secara logis `ExecutionContext`, authoritative
tenant/organization/workspace/actor, role, scope, permission, tool allowlist, classification,
execution budget, memory/evidence references, serta external-research policy dan cost budget.

External retrieval hanya boleh diwujudkan sebagai Backend ToolExecutor adapter. Keputusan GENESIS
`REQUEST_EXTERNAL_RESEARCH` adalah proposal dan tidak melakukan HTTP, egress, permission grant,
scope change, approval, atau release.
