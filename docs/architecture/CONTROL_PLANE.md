# Control Plane dan MCA

Control Plane mengelola proposal capability serta lifecycle digital workforce. Outputnya berupa assessment, draft, finding, evaluation, atau recommendation untuk ALOS Backend.

MCA mengoordinasikan business work pada runtime melalui OrchestrationEngine. Hanya ada satu class `MasterCoordinator`; architecture regression test menegakkan invariant ini.

Control Plane tidak memanggil MCA sebagai workforce manager, dan MCA tidak mengaktifkan Agent/Skill.
