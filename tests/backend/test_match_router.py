"""Integration tests for GET /api/matches."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_matches_200_default() -> None:
    resp = client.get("/api/matches")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_matches_filter_by_year() -> None:
    resp = client.get("/api/matches?years=2022&years=2018")
    assert resp.status_code == 200
    for m in resp.json()["data"]["items"]:
        assert m["tournament_year"] in (2022, 2018)


def test_matches_filter_by_team() -> None:
    resp = client.get("/api/matches?team_ids=team_ARG")
    assert resp.status_code == 200
    for m in resp.json()["data"]["items"]:
        assert m["home_team"]["team_id"] == "team_ARG" or m["away_team"]["team_id"] == "team_ARG"


def test_matches_has_penalties() -> None:
    resp = client.get("/api/matches?has_penalties=true")
    assert resp.status_code == 200
    for m in resp.json()["data"]["items"]:
        assert m["result_type"] == "penalties"


def test_matches_pagination_page_size() -> None:
    resp = client.get("/api/matches?page_size=2&page=1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) <= 2


def test_matches_page_size_gt_100_returns_422() -> None:
    resp = client.get("/api/matches?page_size=200")
    assert resp.status_code == 422


def test_matches_empty_result_200() -> None:
    resp = client.get("/api/matches?years=1930&stages=final&team_ids=team_CHN")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0


def test_matches_penalties_score_separate() -> None:
    resp = client.get("/api/matches?has_penalties=true")
    for m in resp.json()["data"]["items"]:
        score = m["score"]
        if score.get("penalties"):
            assert score["display"] != score.get("penalty_display", "")


def test_matches_applied_filters_echo() -> None:
    resp = client.get("/api/matches?years=2022&team_ids=team_ARG&has_penalties=true")
    af = resp.json()["data"]["applied_filters"]
    assert 2022 in af["years"]
    assert "team_ARG" in af["team_ids"]


def test_openapi_has_matches_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/matches" in schema["paths"]
