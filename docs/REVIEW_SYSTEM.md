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

## Assurance terkini

`CORE_AI_ASSURANCE_REGRESSION_SET` mendeklarasikan `core-ai-assurance-regression`
versi `1.0.0`. Probe context, Skill, memory, runtime, delegation dan research
menentukan PASS/FAIL/NOT_RUN dari fakta bertipe dan evidence. Caller tidak dapat
mengirim boolean PASS sebagai authority. Subject ID/version, correlation dan
set kasus wajib harus cocok; kasus hilang atau NOT_RUN tetap menjadi blocker.

`READY_FOR_IT_REVIEW` berarti siap diajukan, bukan APPROVED, RELEASED atau ACTIVE.
Artefak evaluasi lokal tidak otomatis dipersist atau dikirim ke governance Backend.
Transport/persistence setiap artefak harus dipasang melalui boundary canonical yang
sesuai; fixture deterministik tidak merupakan bukti kualitas model nyata.
