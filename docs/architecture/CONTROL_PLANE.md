# Control Plane dan MCA

Control Plane menghasilkan proposal capability serta assessment digital workforce.
Outputnya berupa draft, finding, evaluation, atau recommendation untuk ALOS Backend.
Lifecycle, persistence, keputusan manusia dan release digital workforce tetap dimiliki Backend.

MCA mengoordinasikan business work pada runtime melalui OrchestrationEngine. Hanya ada satu class `MasterCoordinator`; architecture regression test menegakkan invariant ini.

Control Plane tidak memanggil MCA sebagai workforce manager, dan MCA tidak mengaktifkan Agent/Skill.
