# Peran PydanticAI

PydanticAI merupakan framework yang disetujui untuk integrasi pada adapter, bukan domain model atau authority layer. Wrapper `PydanticAIRuntimeAdapter` lama telah dihapus. Runtime aktif memakai `AgentRuntimeEngine` dan `AgenticPlanner`; pemanggilan model tetap melalui ModelGateway. Dependency framework tidak berarti adapter atau layanan production telah aktif.

Agent tidak dibangun sebagai class per logical identity. Provider-backed Agent yang melewati ModelGateway tidak diizinkan. Model validation Pydantic biasa tetap boleh digunakan pada domain data.
