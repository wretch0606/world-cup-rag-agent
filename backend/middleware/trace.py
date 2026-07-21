"""Trace middleware — generates and propagates trace_id per request."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

# ---------------------------------------------------------------------------
# Context variable — shared between middleware, response factory, and logging
# ---------------------------------------------------------------------------
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

# Allowed characters for client-supplied X-Trace-ID
_TRACE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def get_trace_id() -> str:
    """Return the current request's trace_id (or empty string outside a request)."""
    return _trace_id_var.get()


def _generate_trace_id() -> str:
    """Generate a UUID4 trace_id."""
    return str(uuid.uuid4())


class TraceMiddleware:
    """Pure ASGI middleware: generate or accept X-Trace-ID, store in context var.

    Implemented as plain ASGI (not BaseHTTPMiddleware) to avoid exception
    re-raising issues when ExceptionMiddleware handles downstream errors.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Accept client-supplied trace_id if valid
        headers = dict(scope.get("headers", []))
        client_trace = headers.get(b"x-trace-id", b"").decode("latin-1")
        trace_id = client_trace if _TRACE_ID_RE.match(client_trace) else _generate_trace_id()

        # Store for downstream use
        _trace_id_var.set(trace_id)

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-trace-id", trace_id.encode("latin-1")))
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, send_wrapper)
