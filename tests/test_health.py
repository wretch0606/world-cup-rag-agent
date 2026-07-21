"""Step 02: health endpoint tests — app import, 200, OpenAPI, no forbidden paths."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

# Paths that must NOT exist in this step (step 03+)
FORBIDDEN_PATHS: list[str] = []


def test_app_imports() -> None:
    """App and router objects are importable."""
    assert app is not None
    assert app.title == "world-cup-rag-agent-backend"


def test_health_returns_200() -> None:
    """GET /api/health returns 200 with ApiResponse[HealthData] envelope."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    # Envelope fields
    assert body["success"] is True
    assert body["code"] == "OK"
    # Business data inside envelope
    data = body["data"]
    assert data["status"] == "ok"
    assert data["service"] == "world-cup-rag-agent-backend"
    assert data["version"] == "0.1.0"
    assert data["python"].startswith("3.")


def test_openapi_has_health_path() -> None:
    """The OpenAPI schema contains /api/health."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})
    assert "/api/health" in paths, f"Expected /api/health in OpenAPI paths, got {sorted(paths)}"


def test_no_forbidden_paths() -> None:
    """None of the step 03+ business paths exist yet."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})
    for forbidden in FORBIDDEN_PATHS:
        assert forbidden not in paths, f"Forbidden path {forbidden} should not exist in step 02"


def test_docs_accessible() -> None:
    """Swagger /docs page is reachable."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json_accessible() -> None:
    """/openapi.json returns valid JSON."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
