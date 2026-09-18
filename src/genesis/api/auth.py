"""Service-to-service authentication for GENESIS internal endpoints."""

import secrets
from typing import Annotated

from fastapi import Header, Request


class InternalAuthError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


async def verify_service_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    settings = request.app.state.settings
    configured = settings.ALOS_INTERNAL_TOKEN.get_secret_value()
    if not configured:
        if settings.APP_ENV in {"development", "test"}:
            return
        raise InternalAuthError(
            "INTERNAL_AUTH_NOT_CONFIGURED",
            "GENESIS internal service authentication is not configured.",
            status_code=503,
        )

    expected = f"Bearer {configured}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise InternalAuthError(
            "INTERNAL_AUTH_DENIED",
            "GENESIS internal service authentication failed.",
            status_code=401,
        )
