"""Step 10A.3a: regression tests for OpenAPI response models and contract invariants."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _schema() -> dict:
    return client.get("/openapi.json").json()


def _paths() -> dict:
    return _schema()["paths"]


# ─── 8 endpoints exist ───
def test_eight_endpoints() -> None:
    paths = _paths()
    biz = {p for p in paths if p.startswith("/api/")}
    assert biz == {
        "/api/health",
        "/api/filter-options",
        "/api/matches",
        "/api/matches/{match_id}",
        "/api/teams/{team_id}/relations",
        "/api/graph",
        "/api/documents",
        "/api/agent/query",
    }


# ─── No ApiResponse_dict_ ───
def test_no_api_response_dict() -> None:
    schemas = _schema().get("components", {}).get("schemas", {})
    for name in schemas:
        assert "dict_" not in name, f"Found loose dict schema: {name}"


# ─── No HTTPValidationError ───
def test_no_http_validation_error() -> None:
    schemas = _schema().get("components", {}).get("schemas", {})
    assert "HTTPValidationError" not in schemas, "HTTPValidationError should not appear"


# ─── All 422 are ErrorResponse ───
def test_all_422_are_error_response() -> None:
    paths = _paths()
    for ep, methods in paths.items():
        if not ep.startswith("/api/"):
            continue
        for method in ("get", "post"):
            op = methods.get(method)
            if not op:
                continue
            resp_422 = op.get("responses", {}).get("422")
            if resp_422:
                schema = resp_422.get("content", {}).get(
                    "application/json", {}
                ).get("schema", {})
                ref = schema.get("$ref", "")
                assert "ErrorResponse" in ref, (
                    f"{method.upper()} {ep} 422: got {ref}"
                )


# ─── All 200 are typed ApiResponse ───
def test_all_200_are_typed() -> None:
    paths = _paths()
    for ep, methods in paths.items():
        if not ep.startswith("/api/"):
            continue
        for method in ("get", "post"):
            op = methods.get(method)
            if not op:
                continue
            resp_200 = op.get("responses", {}).get("200")
            if resp_200:
                schema = resp_200.get("content", {}).get(
                    "application/json", {}
                ).get("schema", {})
                ref = schema.get("$ref", "")
                assert "ApiResponse_" in ref, (
                    f"{method.upper()} {ep} 200: got {ref}"
                )


# ─── Runtime: SQLite mode data_status=live (uses fixture DB) ───
def _use_fixture_db(monkeypatch, fixture_db_path: str) -> None:
    """Switch provider to SQLite mode using the test fixture DB."""
    import backend.config
    import backend.dependencies as d

    monkeypatch.setattr(backend.config.settings, "frontend_data_mode", "sqlite")
    monkeypatch.setattr(backend.config.settings, "world_cup_db_path", fixture_db_path)
    d._data_provider = None


def test_matches_data_status_live(monkeypatch, fixture_db_path: str) -> None:
    _use_fixture_db(monkeypatch, fixture_db_path)
    try:
        r = client.get("/api/matches")
        assert r.status_code == 200
        assert r.json()["data"].get("data_status") == "live"
    finally:
        import backend.dependencies as d
        d._data_provider = None


def test_graph_data_status_live(monkeypatch, fixture_db_path: str) -> None:
    _use_fixture_db(monkeypatch, fixture_db_path)
    try:
        r = client.get("/api/graph?limit=10")
        assert r.status_code == 200
        assert r.json()["data"].get("data_status") == "live"
    finally:
        import backend.dependencies as d
        d._data_provider = None


# ─── Runtime: Mock mode data_status=mock ───
def test_filter_options_data_status_mock() -> None:
    r = client.get("/api/filter-options")
    assert r.status_code == 200
    assert r.json()["data"]["data_status"] == "mock"


# ─── Graph no self-loops (fixture DB) ───
def test_graph_no_self_loops(monkeypatch, fixture_db_path: str) -> None:
    _use_fixture_db(monkeypatch, fixture_db_path)
    try:
        r = client.get("/api/graph?limit=200")
        assert r.status_code == 200
        for e in r.json()["data"]["edges"]:
            assert e["source"] != e["target"], (
                f"Self-loop: {e['id']} {e['source']}"
            )
    finally:
        import backend.dependencies as d
        d._data_provider = None


# ─── Draw edge direction: home → away (fixture has M-2022-44 CRO-MAR draw) ───
def test_draw_edge_direction(monkeypatch, fixture_db_path: str) -> None:
    _use_fixture_db(monkeypatch, fixture_db_path)
    try:
        r = client.get("/api/graph?limit=200")
        edges_by_id = {e["match_id"]: e for e in r.json()["data"]["edges"]}
        e = edges_by_id.get("M-2022-44")
        if e:
            assert e["source"] == "team_CRO", (
                f"M-2022-44 draw: expected home=CRO, got {e['source']}"
            )
            assert e["target"] == "team_MAR", (
                f"M-2022-44 draw: expected away=MAR, got {e['target']}"
            )
            assert e["winner_team_id"] is None
    finally:
        import backend.dependencies as d
        d._data_provider = None


# ─── Runtime 422 check ───
def test_422_has_unified_envelope() -> None:
    r = client.get("/api/matches?page_size=999")
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "VALIDATION_ERROR"
    assert "retryable" in body
    assert "details" in body
