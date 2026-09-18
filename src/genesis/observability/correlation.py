from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

correlation_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw = headers.get(b"x-correlation-id")
        correlation_id = raw.decode("ascii", errors="ignore") if raw else f"corr_{uuid4().hex}"
        token = correlation_context.set(correlation_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-correlation-id", correlation_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            correlation_context.reset(token)


def current_correlation_id() -> str:
    """Return the correlation identifier bound to the current request."""

    return correlation_context.get() or f"corr_{uuid4().hex}"
