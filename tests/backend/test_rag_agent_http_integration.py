"""HTTP integration tests: no-API-key behavior (TestClient, no real D/LLM).

Verifies the full HTTP stack handles missing RAG_LLM_API_KEY gracefully:
  - Health endpoint works
  - Exact SQLite queries still return 200
  - Semantic queries return stable errors (no 500 crash)
  - Error messages never leak secrets
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


# ====================================================================
# Helpers
# ====================================================================
def _http_post(client, question, filters=None):
    return client.post(
        "/api/agent/query",
        json={"question": question, "filters": filters or {}},
    )


# ====================================================================
# 1. App can import without API key
# ====================================================================
def test_app_import_without_api_key():
    """Importing main must not crash when RAG_LLM_API_KEY is unset."""
    from backend.main import app  # noqa: F401

    assert True


# ====================================================================
# 2. GET /api/health returns 200
# ====================================================================
def test_health_returns_200():
    from backend.main import app

    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("data", {}).get("status") == "ok"


# ====================================================================
# 3. Exact SQLite query returns 200 without API key
# ====================================================================
def test_exact_query_returns_200_without_key():
    from backend.main import app

    client = TestClient(app)
    resp = _http_post(client, "2022年世界杯决赛比分是多少？")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("data", {}).get("status") != "error"


# ====================================================================
# 4. No crash on any question without API key
# ====================================================================
def test_no_crash_on_varied_questions():
    """Mock mode: all questions return 200, no crash."""
    from backend.main import app

    client = TestClient(app)
    for q in [
        "2022年世界杯决赛比分是多少？",
        "为什么世界杯比赛很经典？",
        "介绍2022年世界杯决赛的重要情节",
        "法国队2018年有哪些比赛？",
    ]:
        resp = _http_post(client, q)
        assert resp.status_code == 200


# ====================================================================
# 4b. LangGraph mode: 503 and 504 tests
# ====================================================================
@patch("backend.application.langgraph_agent_service._get_rag_service")
def test_semantic_no_service_returns_503(_mock_rag):
    _mock_rag.return_value = None
    """Pure rag_query without RAG service -> HTTP 503 via RAGFatalError."""
    from backend.application.langgraph_agent_service import LangGraphAgentService
    from backend.dependencies import get_agent_service
    from backend.main import app

    app.dependency_overrides[get_agent_service] = lambda: LangGraphAgentService()
    client = TestClient(app)
    resp = _http_post(client, "足球比赛为什么激动人心？")
    assert resp.status_code == 503
    data = resp.json()
    assert data["success"] is False
    assert data["code"] == "DATA_SOURCE_UNAVAILABLE"
    assert data["retryable"] is True
    assert data["data"] is None
    assert "trace_id" in data
    assert "timestamp" in data


@patch("backend.application.langgraph_agent_service._get_rag_service")
def test_semantic_retrieval_error_returns_503(_mock_rag):
    """Pure rag_query with retrieval error -> HTTP 503."""
    from backend.application.langgraph_agent_service import LangGraphAgentService
    from backend.dependencies import get_agent_service
    from backend.main import app
    from backend.rag.service import RagService

    class _FailingGateway:
        async def retrieve(self, request):
            raise RuntimeError("boom")

    _mock_rag.return_value = RagService(
        retrieval=_FailingGateway(),
        generation=None,
    )

    app.dependency_overrides[get_agent_service] = lambda: LangGraphAgentService()
    client = TestClient(app)
    resp = _http_post(client, "为什么世界杯比赛很经典？")
    assert resp.status_code == 503
    data = resp.json()
    assert data["success"] is False
    # code can be DATA_SOURCE_UNAVAILABLE (retrieval error mapped)
    assert data["code"] in ("DATA_SOURCE_UNAVAILABLE", "RETRIEVAL_ERROR")
    assert data["retryable"] is True
    assert data["data"] is None


@patch("backend.application.langgraph_agent_service._get_rag_service")
def test_semantic_runtime_error_returns_503(_mock_rag):
    """Pure rag_query with RuntimeError -> HTTP 503 (not 504)."""
    from backend.application.langgraph_agent_service import LangGraphAgentService
    from backend.dependencies import get_agent_service
    from backend.main import app
    from backend.rag.service import RagService

    class _FailingGateway:
        async def retrieve(self, request):
            raise RuntimeError("generic failure")

    _mock_rag.return_value = RagService(
        retrieval=_FailingGateway(),
        generation=None,
    )

    app.dependency_overrides[get_agent_service] = lambda: LangGraphAgentService()
    client = TestClient(app)
    resp = _http_post(client, "为什么世界杯比赛很经典？")
    assert resp.status_code == 503
    data = resp.json()
    assert data["code"] == "DATA_SOURCE_UNAVAILABLE"
    assert data["retryable"] is True


@patch("backend.application.langgraph_agent_service._get_rag_service")
def test_ragresult_timeout_code_returns_504(_mock_rag):
    """RAGResult with error.code=TIMEOUT -> HTTP 504."""
    from backend.application.langgraph_agent_service import LangGraphAgentService
    from backend.dependencies import get_agent_service
    from backend.main import app
    from backend.rag.service import RagService
    from backend.schemas.rag_contract import (  # noqa: F401
        RAG_CONTRACT_VERSION,
        ErrorItem,
        GenerationMeta,
        RAGResult,
        RAGStatus,
        RAGTiming,
        RetrievalFilters,
        RetrievalResult,
        RetrievalTiming,
    )

    class _TimeoutReturningGateway:
        async def retrieve(self, request):
            return RetrievalResult(
                contract_version=RAG_CONTRACT_VERSION,
                trace_id=request.trace_id,
                status=RAGStatus.error,
                original_query=request.query,
                items=[],
                applied_filters=request.filters,
                timing=RetrievalTiming(),
                error=ErrorItem(code="TIMEOUT", message="timeout", component="retrieval"),
            )

    class _DummyGen:
        async def generate(self, req, ret):
            raise RuntimeError("should not be called")

    _mock_rag.return_value = RagService(
        retrieval=_TimeoutReturningGateway(),
        generation=_DummyGen(),
    )

    app.dependency_overrides[get_agent_service] = lambda: LangGraphAgentService()
    client = TestClient(app)
    resp = _http_post(client, "为什么世界杯比赛很经典？")
    assert resp.status_code == 504
    data = resp.json()
    assert data["code"] == "UPSTREAM_TIMEOUT"
    assert data["retryable"] is True


# ====================================================================
# 5. Error message does not contain API key, paths, or stack traces
# ====================================================================
def test_error_message_no_sensitive_content():
    from backend.main import app

    client = TestClient(app)
    resp = _http_post(client, "为什么世界杯比赛很经典？")
    data = resp.json()
    inner = data.get("data") or {}
    all_text = str(data.get("message", "")) + str(inner.get("answer", ""))
    for w in inner.get("warnings", []):
        all_text += str(w.get("message", ""))
    assert "sk-" not in all_text.lower()
    assert "C:\\" not in all_text
    assert "D:\\" not in all_text
    assert "/home/" not in all_text
    assert "Traceback" not in all_text


# ====================================================================
# 6. Warnings have retryable and component when present
# ====================================================================
def test_warnings_have_required_fields():
    from backend.main import app

    client = TestClient(app)
    resp = _http_post(client, "为什么世界杯比赛很经典？")
    data = resp.json()
    inner = data.get("data") or {}
    warnings = inner.get("warnings", [])
    for w in warnings:
        assert "retryable" in w
        assert "component" in w
        assert "code" in w
        assert "message" in w


# ====================================================================
# 7. HTTP response uses ApiResponse envelope
# ====================================================================
def test_response_uses_api_response_envelope():
    from backend.main import app

    client = TestClient(app)
    resp = _http_post(client, "2022年世界杯决赛比分是多少？")
    data = resp.json()
    assert "data" in data
    assert "trace_id" in data
    assert "timestamp" in data


# ====================================================================
# 8. API Key absence confirmed in test environment
# ====================================================================
def test_no_api_key_in_environment():
    """Confirm RAG_LLM_API_KEY is absent during HTTP tests."""
    from backend.config import settings

    assert settings.rag_llm_api_key == ""
