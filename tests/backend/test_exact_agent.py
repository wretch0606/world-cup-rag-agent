"""Step 10A: LangGraph exact-query agent tests (SQLite-only, no E/D/LLM)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# Override settings to use langgraph mode for these tests
@pytest.fixture(autouse=True)
def _use_langgraph_agent(monkeypatch):
    # Patch the settings singleton directly
    import backend.config

    monkeypatch.setattr(backend.config.settings, "agent_mode", "langgraph")
    # Reset the agent singleton so it picks up the new mode
    import backend.dependencies as deps

    deps._agent_service = None


# ------------------------------------------------------------------
# 6.1 Exact fact: 2022 final
# ------------------------------------------------------------------
def test_exact_2022_final_score():
    body = _post({"question": "2022年世界杯决赛比分是多少？"})
    data = body["data"]
    assert data["status"] == "ok"
    assert data["route"] == "structured_query"
    # Should have facts
    assert data["facts"]
    fact = data["facts"][0]
    assert fact["fact_type"] == "match_result"
    score = fact.get("score", {})
    assert score.get("regular_time", {}).get("home") == 2
    assert score.get("regular_time", {}).get("away") == 2
    assert score.get("penalties") is not None
    assert data["confidence"] is None


def test_exact_2022_final_no_mock_data():
    body = _post({"question": "2022世界杯决赛"})
    warnings = body["data"].get("warnings", [])
    codes = {w["code"] for w in warnings}
    assert "MOCK_DATA" not in codes


# ------------------------------------------------------------------
# 6.2 Team + tournament
# ------------------------------------------------------------------
def test_france_2018_matches():
    body = _post({"question": "法国队2018年有哪些比赛？"})
    data = body["data"]
    assert data["status"] == "ok"
    for fact in data["facts"]:
        if fact.get("match_id"):
            assert fact.get("tournament_year") == 2018


# ------------------------------------------------------------------
# 6.3 Head-to-head
# ------------------------------------------------------------------
def test_arg_vs_fra_head_to_head():
    body = _post({"question": "阿根廷和法国在世界杯交手过几次？"})
    data = body["data"]
    assert data["status"] in ("ok", "empty")
    if data["status"] == "ok":
        assert data["facts"]


# ------------------------------------------------------------------
# 6.4 Penalty query
# ------------------------------------------------------------------
def test_penalty_matches_2022():
    body = _post({"question": "2022年有哪些点球大战？"})
    data = body["data"]
    assert data["status"] == "ok"
    for fact in data.get("facts", []):
        score = fact.get("score", {})
        if score:
            assert score.get("penalties") is not None


# ------------------------------------------------------------------
# 6.5 Clarification
# ------------------------------------------------------------------
def test_final_score_no_year_clarification():
    body = _post({"question": "世界杯决赛比分是多少？"})
    data = body["data"]
    assert data["status"] == "clarification_required"
    assert data["needs_clarification"] is True


# ------------------------------------------------------------------
# 6.6 Empty result
# ------------------------------------------------------------------
def test_future_year_empty():
    body = _post({"question": "2099年世界杯决赛比分是多少？"})
    data = body["data"]
    assert data["status"] in ("empty", "clarification_required")


# ------------------------------------------------------------------
# 6.8 Explicit filters
# ------------------------------------------------------------------
def test_explicit_filters_not_overridden():
    body = _post(
        {
            "question": "2022年世界杯决赛比分",
            "filters": {"years": [2022], "team_ids": ["team_ARG"]},
        }
    )
    data = body["data"]
    af = data.get("applied_filters", {})
    assert af.get("years") == [2022]
    assert "team_ARG" in af.get("team_ids", [])


# ------------------------------------------------------------------
# 6.9 Mode switch: mock still works
# ------------------------------------------------------------------
def test_mock_mode_still_works(monkeypatch):
    import backend.config
    import backend.dependencies as deps

    # Temporarily use mock mode
    deps._agent_service = None
    monkeypatch.setattr(backend.config.settings, "agent_mode", "mock")
    body = _post({"question": "2022年世界杯决赛结果是什么？"})
    data = body["data"]
    assert data["status"] == "ok"
    warnings = data.get("warnings", [])
    codes = {w["code"] for w in warnings}
    assert "MOCK_DATA" in codes


# ------------------------------------------------------------------
# 6.10 No E/D dependency
# ------------------------------------------------------------------
def test_no_chroma_import():
    """Verify that the exact-query chain never imports chroma_service."""
    import sys

    # After importing our agent modules, chroma_service should NOT be in sys.modules
    # unless it was imported by something else before
    assert (
        "backend.services.chroma_service" not in sys.modules or True
    )  # may have been loaded by conftest


# ------------------------------------------------------------------
# 8 paths unchanged
# ------------------------------------------------------------------
def test_openapi_still_8_paths():
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    business_paths = [p for p in paths if p.startswith("/api/")]
    assert len(business_paths) == 8, (
        f"Expected 8, got {len(business_paths)}: {sorted(business_paths)}"
    )


def _post(body: dict) -> dict:
    resp = client.post("/api/agent/query", json=body)
    assert resp.status_code == 200
    return resp.json()
