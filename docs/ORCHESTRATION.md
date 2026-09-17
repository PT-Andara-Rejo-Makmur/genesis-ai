# Orchestration

## GENESIS dan MCA

Control Plane mengelola workforce lifecycle. MCA adalah satu-satunya master business orchestrator. Keduanya tidak saling menduplikasi.

Eksekusi Agent sederhana langsung menggunakan AgentRuntime. LangGraph dipakai hanya untuk workflow multi-step, parent-child delegation, pause/resume, stateful execution, authority gate, serta checkpoint/recovery.

## Delegation

Setiap child membawa `root_run_id`, `parent_run_id`, dan `depth`. DelegationGuard menegakkan:

- tenant dan workspace sama dengan parent;
- permission, scope, dan tool child merupakan subset parent;
- budget child tidak melebihi parent;
- `max_depth`, `max_children`, dan timeout;
- cycle prevention melalui ancestry Agent;
- structured child result untuk synthesis.

Child tidak pernah memperoleh authority lebih besar daripada parent. Human/authority gate tetap diselesaikan oleh ALOS Backend.
