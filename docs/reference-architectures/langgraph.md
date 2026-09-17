# Peran LangGraph

LangGraph digunakan sebagai adapter OrchestrationEngine untuk workflow stateful yang memerlukan beberapa langkah, delegation, pause/resume, checkpoint/recovery, atau human gate.

Graph bukan default untuk setiap Agent call. Agent execution sederhana menggunakan AgentRuntime. State graph tidak boleh menyimpan approval authoritative; authority gate diteruskan ke ALOS Backend.
