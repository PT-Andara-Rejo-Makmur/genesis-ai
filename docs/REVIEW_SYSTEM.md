# Sistem Review

GENESIS menyediakan lima AI review: business, technical, security, evidence, serta cost/risk. Setiap engine menghasilkan AIReviewResult dengan status:

- `READY`
- `REVISION_RECOMMENDED`
- `BLOCKED_BY_EVIDENCE`
- `RISK_FOUND`

Status `APPROVED_BY_AI` tidak ada dan ditolak oleh model. Hasil review digabungkan menjadi draft yang dipetakan ke ReviewPackage kanonis dari `alos-contracts`.

```text
Automated QA / AI Review
           |
           v
 ReviewPackage recommendation
           |
           v
       IT decision
           |
           v
    Director decision
```

Keputusan IT dan Director disimpan secara authoritative oleh ALOS Backend. GENESIS tidak dapat mengubah release state.
