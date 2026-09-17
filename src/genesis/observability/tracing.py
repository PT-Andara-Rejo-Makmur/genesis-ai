from opentelemetry import trace


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("genesis-ai")
