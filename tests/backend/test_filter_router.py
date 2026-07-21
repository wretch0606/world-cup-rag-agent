"""Integration tests for GET /api/filter-options."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_filter_options_200() -> None:
    resp = client.get("/api/filter-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == "OK"


def test_filter_options_has_data_status() -> None:
    resp = client.get("/api/filter-options")
    data = resp.json()["data"]
    assert "data_status" in data
    assert data["data_status"] in ("mock", "live")


def test_filter_options_has_8_stages() -> None:
    resp = client.get("/api/filter-options")
    stages = resp.json()["data"]["stages"]
    assert len(stages) == 8
    values = {s["value"] for s in stages}
    assert "second_group" in values
    assert "final_round" in values


def test_filter_options_teams_have_team_id() -> None:
    resp = client.get("/api/filter-options")
    for t in resp.json()["data"]["teams"]:
        assert t["team_id"].startswith("team_")
        assert "name" in t


def test_filter_options_tournaments_sorted() -> None:
    resp = client.get("/api/filter-options")
    years = [t["year"] for t in resp.json()["data"]["tournaments"]]
    assert years == sorted(years, reverse=True)


def test_filter_options_stages_sorted_by_order() -> None:
    resp = client.get("/api/filter-options")
    orders = [s["order"] for s in resp.json()["data"]["stages"]]
    assert orders == sorted(orders)


def test_openapi_has_filter_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/filter-options" in schema["paths"]
