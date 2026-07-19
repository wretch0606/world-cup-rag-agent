"""Integration tests for GET /api/teams/{team_id}/relations."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_team_relations_200() -> None:
    resp = client.get("/api/teams/team_ARG/relations")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["team"]["team_id"] == "team_ARG"
    assert "stats" in data
    assert "matches" in data
    assert "graph" in data


def test_team_relations_stats() -> None:
    resp = client.get("/api/teams/team_ARG/relations")
    stats = resp.json()["data"]["stats"]
    assert "matches" in stats
    assert "regulation_or_extra_time_wins" in stats
    assert "draws" in stats
    assert "penalty_advances" in stats
    assert "losses" in stats


def test_team_relations_with_filter() -> None:
    resp = client.get("/api/teams/team_ARG/relations?year_from=2018&year_to=2022")
    assert resp.status_code == 200
    for m in resp.json()["data"]["matches"]:
        assert 2018 <= m["tournament_year"] <= 2022


def test_team_relations_penalties_only() -> None:
    resp = client.get("/api/teams/team_ARG/relations?has_penalties=true")
    assert resp.status_code == 200
    for m in resp.json()["data"]["matches"]:
        assert m["result_type"] == "penalties"


def test_team_not_found_404() -> None:
    resp = client.get("/api/teams/team_XXX/relations")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "TEAM_NOT_FOUND"
    assert body["retryable"] is False


def test_openapi_has_team_relations_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/teams/{team_id}/relations" in schema["paths"]
