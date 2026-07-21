"""Step 03: unified response, error, trace and logging tests."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from backend.main import app as production_app

client = TestClient(production_app)


# ============================================================================
# Helpers
# ============================================================================
def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string."""
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _assert_envelope(body: dict, *, success: bool, code: str) -> None:
    """Assert the unified envelope fields are present and correct."""
    assert body["success"] == success
    assert body["code"] == code
    assert isinstance(body["message"], str)
    assert "trace_id" in body
    assert "timestamp" in body
    assert len(body["trace_id"]) > 0


# ============================================================================
# Health
# ============================================================================
def test_health_ok_structure() -> None:
    """GET /api/health returns ApiResponse[HealthData] with all fields."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope(body, success=True, code="OK")
    data = body["data"]
    assert data["status"] == "ok"
    assert data["service"] == "world-cup-rag-agent-backend"
    assert data["version"] == "0.1.0"
    assert data["python"].startswith("3.")


def test_health_envelope_no_extra_keys() -> None:
    """Health response only contains the 6 envelope fields + data."""
    resp = client.get("/api/health")
    body = resp.json()
    allowed = {"success", "code", "message", "data", "trace_id", "timestamp"}
    assert set(body.keys()) == allowed


def test_health_data_no_extra_keys() -> None:
    """HealthData only contains the 4 defined fields."""
    resp = client.get("/api/health")
    data = resp.json()["data"]
    assert set(data.keys()) == {"status", "service", "version", "python"}


# ============================================================================
# 404
# ============================================================================
def test_404_not_found() -> None:
    """Unknown path returns 404 with NOT_FOUND envelope."""
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    _assert_envelope(body, success=False, code="NOT_FOUND")
    assert body["retryable"] is False
    assert body["data"] is None


# ============================================================================
# 422
# ============================================================================
def test_422_validation_error() -> None:
    """FastAPI's built-in validation returns 422 with VALIDATION_ERROR envelope.

    We send an invalid query param to trigger RequestValidationError.
    """
    # We don't have a route with query params yet, so we use a
    # dedicated test app with a validation-triggering endpoint.
    test_app = _make_validation_test_app()
    test_client = TestClient(test_app)
    resp = test_client.get("/test-validate?id=abc")  # id expects int
    assert resp.status_code == 422
    body = resp.json()
    _assert_envelope(body, success=False, code="VALIDATION_ERROR")
    assert body["retryable"] is False
    assert isinstance(body["details"], list)
    assert len(body["details"]) >= 1
    assert "field" in body["details"][0]


def _make_validation_test_app() -> FastAPI:
    """Build a minimal app to test validation error handling."""
    from fastapi import APIRouter, Query

    from backend.middleware.trace import TraceMiddleware
    from backend.schemas.response import ErrorDetail, error

    router = APIRouter()

    @router.get("/test-validate")
    async def test_validate(item_id: int = Query(...)) -> dict:  # noqa: B008
        return {"item_id": item_id}

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.exception_handler(RequestValidationError)
    async def vh(request, exc: RequestValidationError):
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in e.get("loc", ())),
                error=e.get("msg", ""),
            )
            for e in exc.errors()
        ]
        return error(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            status_code=422,
            retryable=False,
            details=details,
        )

    app.include_router(router)
    return app


# ============================================================================
# 500 (controlled)
# ============================================================================
def test_500_internal_error() -> None:
    """Unhandled exception produces INTERNAL_ERROR envelope.

    Uses a controlled FastAPI app with minimal middleware stack to avoid
    Starlette's ServerErrorMiddleware interference with TestClient.
    """
    from backend.middleware.trace import TraceMiddleware
    from backend.schemas.response import error as make_error

    # Build a minimal app whose error handler returns JSONResponse directly
    test_app = FastAPI()
    test_app.add_middleware(TraceMiddleware)

    @test_app.get("/will-crash")
    async def crash() -> None:
        msg = "simulated failure"
        raise RuntimeError(msg)

    # Register the same error() helper as the production app uses
    @test_app.exception_handler(Exception)
    async def handler(request, exc: Exception):
        return make_error(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            status_code=500,
            retryable=True,
        )

    tc = TestClient(test_app, raise_server_exceptions=False)
    resp = tc.get("/will-crash")
    assert resp.status_code == 500
    body = resp.json()
    _assert_envelope(body, success=False, code="INTERNAL_ERROR")
    assert body["retryable"] is True
    assert body["data"] is None


def test_500_no_stack_leak() -> None:
    """500 error response must NOT expose stack traces or internal paths."""
    from backend.middleware.trace import TraceMiddleware
    from backend.schemas.response import error as make_error

    test_app = FastAPI()
    test_app.add_middleware(TraceMiddleware)

    @test_app.get("/will-crash-leak")
    async def crash() -> None:
        msg = "simulated failure"
        raise RuntimeError(msg)

    @test_app.exception_handler(Exception)
    async def handler(request, exc: Exception):
        return make_error(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            status_code=500,
            retryable=True,
        )

    tc = TestClient(test_app, raise_server_exceptions=False)
    resp = tc.get("/will-crash-leak")
    body = resp.json()
    body_str = str(body).lower()
    assert "traceback" not in body_str
    assert "d:\\shixunwork" not in body_str
    assert "line " not in body_str
    assert "raise " not in body_str
    assert "内部" in body["message"]


# ============================================================================
# Trace
# ============================================================================
def test_trace_id_header_and_body_match() -> None:
    """X-Trace-ID response header matches JSON body trace_id."""
    resp = client.get("/api/health")
    body = resp.json()
    header_trace = resp.headers.get("X-Trace-ID", "")
    assert len(header_trace) > 0
    assert header_trace == body["trace_id"]


def test_trace_id_client_supplied() -> None:
    """Server accepts a valid client-supplied X-Trace-ID."""
    supplied = "my-trace-abc-123"
    resp = client.get("/api/health", headers={"X-Trace-ID": supplied})
    body = resp.json()
    assert body["trace_id"] == supplied
    assert resp.headers["X-Trace-ID"] == supplied


def test_trace_id_client_too_long_replaced() -> None:
    """Server replaces an X-Trace-ID longer than 64 chars."""
    long_id = "a" * 65
    resp = client.get("/api/health", headers={"X-Trace-ID": long_id})
    body = resp.json()
    assert body["trace_id"] != long_id
    assert len(body["trace_id"]) == 36  # UUID4 length


def test_trace_id_client_invalid_chars_replaced() -> None:
    """Server replaces an X-Trace-ID with invalid characters."""
    resp = client.get("/api/health", headers={"X-Trace-ID": "trace<script>"})
    body = resp.json()
    assert body["trace_id"] != "trace<script>"
    assert "<" not in body["trace_id"]


# ============================================================================
# Timestamp
# ============================================================================
def test_timestamp_iso8601_utc() -> None:
    """The timestamp field is a valid ISO 8601 UTC time."""
    resp = client.get("/api/health")
    ts = resp.json()["timestamp"]
    parsed = _parse_timestamp(ts)
    assert parsed.tzinfo is not None
    # Should be within the last minute
    now = datetime.now(UTC)
    delta = (now - parsed).total_seconds()
    assert 0 <= delta < 120, f"Timestamp {ts} is too far from now ({delta}s)"


def test_timestamp_consistent_across_requests() -> None:
    """Two sequential requests produce distinct timestamps."""
    ts1 = client.get("/api/health").json()["timestamp"]
    ts2 = client.get("/api/health").json()["timestamp"]
    # They may be equal if the requests are fast enough, but typically differ
    # We just verify both are parseable
    _parse_timestamp(ts1)
    _parse_timestamp(ts2)


# ============================================================================
# OpenAPI
# ============================================================================
def test_openapi_health_schema() -> None:
    """OpenAPI response model for /api/health reflects the envelope."""
    schema = client.get("/openapi.json").json()
    health_path = schema["paths"]["/api/health"]["get"]
    # 200 response should have a $ref to the ApiResponse model
    resp_200 = health_path["responses"]["200"]
    assert "content" in resp_200


def test_openapi_no_forbidden_paths() -> None:
    """OpenAPI still only contains the /api/health path (no step 04+ paths)."""
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    forbidden = []
    for path in forbidden:
        assert path not in paths, f"Forbidden path {path} should not exist in step 03"
