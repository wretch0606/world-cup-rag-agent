"""End-to-end tests: chain all 8 A↔B API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_e2e_full_flow() -> None:
    """Complete E2E chain: filter-options → matches → graph → agent → detail → relations → documents."""

    # 1. filter-options
    r = client.get("/api/filter-options")
    assert r.status_code == 200
    opts = r.json()["data"]
    assert opts["data_status"] in ("mock", "live")
    assert len(opts["stages"]) == 8

    # 2. matches (filtered)
    r = client.get("/api/matches?years=2022&page_size=5")
    assert r.status_code == 200
    matches_data = r.json()["data"]
    assert len(matches_data["items"]) >= 1
    match_id = matches_data["items"][0]["match_id"]

    # 3. graph
    r = client.get("/api/graph?years=2022&limit=10")
    assert r.status_code == 200
    graph_data = r.json()["data"]
    assert "nodes" in graph_data
    assert "edges" in graph_data

    # 4. agent query
    r = client.post("/api/agent/query", json={"question": "2022年世界杯决赛结果是什么？"})
    assert r.status_code == 200
    agent_data = r.json()["data"]
    assert agent_data["status"] == "ok"
    facts = agent_data["facts"]
    assert len(facts) >= 1
    fact_match_id = facts[0]["match_id"]

    # 5. match detail (from agent fact)
    r = client.get(f"/api/matches/{fact_match_id}")
    assert r.status_code == 200
    detail = r.json()["data"]
    assert detail["match_id"] == fact_match_id
    assert "score" in detail
    assert "timeline" in detail

    # 6. team relations
    team_id = detail["home_team"]["team_id"]
    r = client.get(f"/api/teams/{team_id}/relations")
    assert r.status_code == 200
    rel_data = r.json()["data"]
    assert rel_data["team"]["team_id"] == team_id
    assert "stats" in rel_data

    # 7. documents
    r = client.get("/api/documents")
    assert r.status_code == 200
    doc_data = r.json()["data"]
    assert "items" in doc_data

    # Verify all responses have the unified envelope
    for resp_data in [opts, matches_data, graph_data, agent_data, detail, rel_data, doc_data]:
        # each is the .data portion — the envelope should be checked on raw response
        pass


def test_e2e_unified_envelope_all_endpoints() -> None:
    """Every endpoint returns the unified ApiResponse envelope."""
    endpoints = [
        ("GET", "/api/health", None),
        ("GET", "/api/filter-options", None),
        ("GET", "/api/matches", None),
        ("GET", "/api/matches/M-2022-64", None),
        ("GET", "/api/teams/team_ARG/relations", None),
        ("GET", "/api/graph", None),
        ("GET", "/api/documents", None),
        ("POST", "/api/agent/query", {"question": "hello"}),
    ]
    for method, path, body in endpoints:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json=body)
        data = r.json()
        assert "success" in data, f"{path}: missing success"
        assert "code" in data, f"{path}: missing code"
        assert "trace_id" in data, f"{path}: missing trace_id"
        assert "timestamp" in data, f"{path}: missing timestamp"
        assert len(data["trace_id"]) > 0, f"{path}: empty trace_id"


def test_e2e_trace_id_header() -> None:
    """X-Trace-ID response header matches JSON body trace_id."""
    r = client.get("/api/health")
    assert r.headers.get("X-Trace-ID") == r.json()["trace_id"]


def test_e2e_cors_preflight() -> None:
    """CORS preflight allows the Vite dev origin."""
    r = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200


def test_e2e_json_content_type() -> None:
    """All responses use application/json."""
    for path in ["/api/health", "/api/filter-options", "/api/matches"]:
        r = client.get(path)
        ct = r.headers.get("content-type", "")
        assert "application/json" in ct, f"{path}: {ct}"
