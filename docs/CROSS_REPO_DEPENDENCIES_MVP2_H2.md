# CROSS_REPO_DEPENDENCIES — MVP2 H2 AI

## `alos-contracts`

Canonical `ExecutionContext` dan `ContextBundle` sudah digunakan dan divalidasi. Contract
`ContextBundle` v1 saat ini belum memuat goal, capability, allowed tools, execution budget,
memory references, serta metadata selected/dropped context. GENESIS memakai typed runtime wrapper
dan menghasilkan projection `ContextBundle` v1 yang canonical; tidak ada schema shared permanen
yang disalin ke repository ini.

Next action pemilik `alos-contracts`: evaluasi versi contract baru untuk runtime ContextBundle dan
structured external-research decision sebelum object tersebut menjadi public cross-repo API.

## `alos-backend`

Backend harus tetap membentuk dan menandatangani secara logis `ExecutionContext`, authoritative
tenant/organization/workspace/actor, role, scope, permission, tool allowlist, classification,
execution budget, memory/evidence references, serta external-research policy dan cost budget.

External retrieval hanya boleh diwujudkan sebagai Backend ToolExecutor adapter. Keputusan GENESIS
`REQUEST_EXTERNAL_RESEARCH` adalah proposal dan tidak melakukan HTTP, egress, permission grant,
scope change, approval, atau release.
