"""Structured request-logging middleware."""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from backend.middleware.trace import get_trace_id

logger = logging.getLogger("backend.request")


class LoggingMiddleware:
    """Pure ASGI middleware: log method, path, status, trace_id, duration_ms.

    Does NOT log request bodies, headers, or query parameters to avoid
    leaking secrets, API keys, or future prompt text.

    Implemented as plain ASGI (not BaseHTTPMiddleware) to avoid exception
    re-raising issues when ExceptionMiddleware handles downstream errors.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code: int = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.info(
                "method=%s path=%s status=%d trace_id=%s duration_ms=%d",
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                get_trace_id(),
                duration_ms,
            )
