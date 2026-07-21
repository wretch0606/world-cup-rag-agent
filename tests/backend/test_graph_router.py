"""Integration tests for GET /api/graph."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_graph_200() -> None:
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "nodes" in data
    assert "edges" in data
    assert "stats" in data


def test_graph_nodes_referenced_by_edges() -> None:
    resp = client.get("/api/graph")
    data = resp.json()["data"]
    node_ids = {n["id"] for n in data["nodes"]}
    for e in data["edges"]:
        assert e["source"] in node_ids
        assert e["target"] in node_ids


def test_graph_edges_have_match_id() -> None:
    resp = client.get("/api/graph")
    for e in resp.json()["data"]["edges"]:
        assert e["match_id"].startswith("M-")
        assert e["id"] == f"edge-{e['match_id']}"


def test_graph_filter_by_year() -> None:
    resp = client.get("/api/graph?years=2022")
    for e in resp.json()["data"]["edges"]:
        assert e["tournament_year"] == 2022


def test_graph_has_penalties() -> None:
    resp = client.get("/api/graph?has_penalties=true")
    for e in resp.json()["data"]["edges"]:
        assert e["result_type"] == "penalties"


def test_graph_limit() -> None:
    resp = client.get("/api/graph?limit=1")
    data = resp.json()["data"]
    assert len(data["edges"]) <= 1


def test_graph_direction() -> None:
    """Winner→loser or home→away for draws."""
    resp = client.get("/api/graph")
    for e in resp.json()["data"]["edges"]:
        if e["winner_team_id"]:
            assert e["source"] == e["winner_team_id"]


def test_openapi_has_graph_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/graph" in schema["paths"]
