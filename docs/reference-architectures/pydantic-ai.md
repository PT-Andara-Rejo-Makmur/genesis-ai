# Peran PydanticAI

PydanticAI digunakan sebagai adapter Agent runtime, bukan domain model atau authority layer. Domain bergantung pada `AgentRuntime`; `PydanticAIRuntimeAdapter` menerjemahkan Definition dan RunInput kepada invoker PydanticAI yang harus menggunakan model berbasis ModelGateway.

Agent tidak dibangun sebagai class per logical identity. Provider-backed Agent yang melewati ModelGateway tidak diizinkan. Model validation Pydantic biasa tetap boleh digunakan pada domain data.
