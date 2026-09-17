# ADR-003: ModelGateway Tunggal

- Status: Diterima
- Tanggal: 2026-09-16

## Keputusan

Seluruh model access melewati ModelGateway dengan urutan policy, budget, route, adapter, dan provider. Agent domain tidak boleh mengimpor provider SDK.

## Konsekuensi

Cost, safety policy, routing, correlation, dan observability dapat diberlakukan secara konsisten.
