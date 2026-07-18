"""Unified API response models (Pydantic v2) and factory functions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from starlette.responses import JSONResponse

from backend.middleware.trace import get_trace_id

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Unified response envelope for all front-end API endpoints."""

    success: bool
    code: str
    message: str
    data: T | None = None
    trace_id: str
    timestamp: str

    model_config = {"extra": "forbid"}


class ErrorDetail(BaseModel):
    """Single field-level or item-level validation error detail."""

    field: str | None = None
    error: str


def _now_utc_iso() -> str:
    """Return current UTC time as ISO 8601 string with 'Z' suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ok(data: T, code: str = "OK", message: str = "查询成功") -> ApiResponse[T]:
    """Build a successful response."""
    return ApiResponse(
        success=True,
        code=code,
        message=message,
        data=data,
        trace_id=get_trace_id(),
        timestamp=_now_utc_iso(),
    )


def error(
    code: str,
    message: str,
    *,
    status_code: int = 500,
    retryable: bool = False,
    details: list[ErrorDetail] | None = None,
    data: Any = None,
) -> JSONResponse:
    """Build an error JSONResponse for use in exception handlers.

    Exception handlers in FastAPI/Starlette MUST return a Response object,
    not a plain dict — otherwise ``'dict' object is not callable`` is raised.
    """
    body: dict[str, Any] = {
        "success": False,
        "code": code,
        "message": message,
        "data": data,
        "trace_id": get_trace_id(),
        "timestamp": _now_utc_iso(),
        "retryable": retryable,
        "details": [d.model_dump() if isinstance(d, ErrorDetail) else d for d in (details or [])],
    }
    return JSONResponse(content=body, status_code=status_code)
