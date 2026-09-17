# ADR-001: Isolasi Framework

- Status: Diterima
- Tanggal: 2026-09-16

## Keputusan

Domain menggunakan Protocol dan tidak mengimpor PydanticAI, LangGraph, MCP, atau provider. Integrasi framework hanya berada di `adapters/`.

## Konsekuensi

Framework dapat diganti atau di-upgrade tanpa mengubah capability, authority, delegation, review, dan research domain.
