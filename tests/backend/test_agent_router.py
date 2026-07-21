"""Integration tests for POST /api/agent/query."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _post(body: dict) -> dict:
    resp = client.post("/api/agent/query", json=body)
    return resp.json()


# ---- 200: known fact ----
def test_agent_2022_final() -> None:
    body = _post({"question": "2022年世界杯决赛结果是什么？"})
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "ok"
    assert data["intent"] == "match_result_query"
    assert data["facts"]
    fact = data["facts"][0]
    assert fact["match_id"] == "M-2022-64"
    assert fact["fact_type"] == "match_result"


def test_agent_2022_final_graph() -> None:
    body = _post({"question": "2022世界杯决赛"})
    graph = body["data"]["graph"]
    assert graph["scope"] == "answer_facts"
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["match_id"] == "M-2022-64"


# ---- 200: clarification ----
def test_agent_clarification() -> None:
    body = _post({"question": "决赛结果是什么？"})
    data = body["data"]
    assert data["status"] == "clarification_required"
    assert data["needs_clarification"] is True
    assert data["clarification_question"]


# ---- 200: general chat ----
def test_agent_greeting() -> None:
    body = _post({"question": "你好"})
    data = body["data"]
    assert data["intent"] == "general_chat"
    assert data["route"] == "general_chat"
    assert data["status"] == "ok"


# ---- 200: empty ----
def test_agent_empty() -> None:
    body = _post({"question": "中国队2022世界杯成绩如何？"})
    data = body["data"]
    assert data["status"] == "empty"
    assert data["facts"] == []


# ---- Validation ----
def test_agent_empty_question_422() -> None:
    resp = client.post("/api/agent/query", json={"question": ""})
    assert resp.status_code == 422


def test_agent_too_long_422() -> None:
    resp = client.post("/api/agent/query", json={"question": "x" * 2001})
    assert resp.status_code == 422


def test_agent_unknown_field_422() -> None:
    resp = client.post("/api/agent/query", json={"question": "hi", "unknown": True})
    assert resp.status_code == 422


# ---- Mock data markers ----
def test_agent_mock_warning() -> None:
    body = _post({"question": "2022决赛"})
    warnings = body["data"]["warnings"]
    codes = {w["code"] for w in warnings}
    assert "MOCK_DATA" in codes


def test_agent_confidence_null() -> None:
    body = _post({"question": "2022决赛"})
    assert body["data"]["confidence"] is None


def test_agent_filter_echo() -> None:
    body = _post(
        {
            "question": "2022决赛",
            "filters": {"years": [2022], "team_ids": ["team_ARG"]},
        }
    )
    af = body["data"]["applied_filters"]
    assert af["years"] == [2022]
    assert "team_ARG" in af["team_ids"]


def test_openapi_has_agent_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/agent/query" in schema["paths"]
