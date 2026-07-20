"""Integration tests: LangGraph agent with RAG routing (no real D/LLM).

Verifies semantic/hybrid queries enter RAG nodes, exact queries stay
on SQLite path, and RAGResult → AgentQueryData mapping works.
"""
from __future__ import annotations

from unittest.mock import patch

from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    EvidenceItem,
    GenerationMeta,
    MatchResultFact,
    RAGResult,
    RAGStatus,
    RAGTiming,
    RetrievalResult,
    RetrievalTiming,
    SourceItem,
    WarningItem,
)


# ====================================================================
# Fake RAG gateways
# ====================================================================
class FakeRetrievalGateway:
    def __init__(self, *, items=None, status=RAGStatus.ok, warnings=None,
                 error=None):
        self.items = items or []
        self.status = status
        self._warnings = warnings or []
        self.last_request = None

    async def retrieve(self, request):
        self.last_request = request
        return RetrievalResult(
            contract_version=RAG_CONTRACT_VERSION, trace_id=request.trace_id,
            status=self.status, original_query=request.query, items=self.items,
            applied_filters=request.filters, rewrite_applied=False,
            rerank_applied=False, warnings=self._warnings,
            timing=RetrievalTiming(retrieval_ms=10, total_ms=10),
        )


class FakeGenerationClient:
    def __init__(self, *, answer="RAG 测试回答。", facts=None, sources=None,
                 status=RAGStatus.ok, warnings=None):
        self.answer = answer
        self._facts = facts or []
        self._sources = sources or []
        self._status = status
        self._warnings = warnings or []
        self.last_request = None

    async def generate(self, request, retrieval):
        self.last_request = (request, retrieval)
        return RAGResult(
            contract_version=RAG_CONTRACT_VERSION, trace_id=request.trace_id,
            status=self._status, answer=self.answer, facts=self._facts,
            sources=self._sources, evidence=retrieval.items,
            applied_filters=retrieval.applied_filters, confidence=None,
            rewrite_applied=False, rerank_applied=False,
            warnings=self._warnings,
            timing=RAGTiming(generation_ms=50, total_ms=100),
            generation_meta=GenerationMeta(model_name="test-model"), error=None,
        )


def _make_fake_rag_service(retrieval=None, generation=None):
    from backend.rag.service import RagService
    return RagService(
        retrieval=retrieval or FakeRetrievalGateway(),
        generation=generation or FakeGenerationClient(),
    )


# ====================================================================
def _invoke_agent(question, filters=None, trace_id="test-trace",
                  rag_service="NOT_SET"):
    import importlib

    import backend.application.langgraph_agent_service as agent_mod
    importlib.reload(agent_mod)

    svc = agent_mod.LangGraphAgentService()
    request = {"question": question, "session_id": None,
               "filters": filters or {}}

    if rag_service == "NOT_SET":
        # Default: block RAG to prevent accidental real Chroma init
        with patch.object(agent_mod, "_get_rag_service", return_value=None):
            return svc.query(request, trace_id)
    else:
        with patch.object(agent_mod, "_get_rag_service", return_value=rag_service):
            return svc.query(request, trace_id)


# ====================================================================
# Helpers to create fake services for RAG-aware tests
# ====================================================================
def _mk_ev():
    return EvidenceItem(chunk_id="c1", document_id="d1", source_id="s1",
                        document_name="D", text="evidence", data_version="v1",
                        retrieval_rank=1)

def _mk_svc(answer="OK", facts=None, sources=None, status=RAGStatus.ok):
    ret = FakeRetrievalGateway(items=[_mk_ev()])
    gen = FakeGenerationClient(answer=answer, facts=facts or [],
                               sources=sources or [], status=status)
    return _make_fake_rag_service(retrieval=ret, generation=gen), ret, gen


# ====================================================================
# 1. Exact score stays on exact_query path
# ====================================================================
def test_exact_score_stays_exact():
    result = _invoke_agent("2022年世界杯决赛比分是多少？")
    assert result["route"] == "structured_query"
    assert result["intent"] == "match_result_query"


# ====================================================================
# 2,3. Exact score never calls RetrievalGateway or GenerationClient
# ====================================================================
def test_exact_score_no_rag_calls():
    rag_svc, ret, gen = _mk_svc()
    result = _invoke_agent("2022年世界杯决赛比分是多少？",
                           rag_service=rag_svc)
    assert result["route"] == "structured_query"
    assert ret.last_request is None
    assert gen.last_request is None


# ====================================================================
# 4. Pure semantic question enters rag_query
# ====================================================================
def test_semantic_question_enters_rag():
    """No year/team/stage keyword → pure rag_query."""
    result = _invoke_agent("足球比赛为什么激动人心？")
    assert result["route"] == "rag_query"


# ====================================================================
# 5. Semantic calls RagService once
# ====================================================================
def test_semantic_calls_rag_service():
    rag_svc, ret, gen = _mk_svc(answer="经典比赛分析。",
                                sources=[SourceItem(source_id="s1", title="T")])
    result = _invoke_agent("足球比赛为什么激动人心？", rag_service=rag_svc)
    assert result["route"] == "rag_query"
    assert ret.last_request is not None
    assert gen.last_request is not None
    assert result["answer"]


# ====================================================================
# 6. Hybrid query routing
# ====================================================================
def test_hybrid_query_route():
    result = _invoke_agent("介绍2022年阿根廷的表现")
    assert result["route"] in ("hybrid_query", "rag_query")


# ====================================================================
# 7. trace_id passthrough
# ====================================================================
def test_trace_id_passthrough():
    rag_svc, ret, gen = _mk_svc()
    _invoke_agent("介绍2022年世界杯决赛的重要情节",
                  trace_id="my-custom-trace", rag_service=rag_svc)
    assert ret.last_request is not None
    assert ret.last_request.trace_id == "my-custom-trace"


# ====================================================================
# 8-11. Status mappings
# ====================================================================
def test_rag_status_ok_mapping():
    rag_svc, _, _ = _mk_svc(answer="OK", status=RAGStatus.ok)
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert result["status"] == "ok"


def test_rag_status_empty_mapping():
    ret = FakeRetrievalGateway(items=[], status=RAGStatus.empty)
    gen = FakeGenerationClient(answer="empty", status=RAGStatus.empty,
                               warnings=[WarningItem(code="NO_RESULT",
                               message="x", component="retrieval")])
    rag_svc = _make_fake_rag_service(retrieval=ret, generation=gen)
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert result["status"] in ("empty", "degraded")


def test_rag_status_degraded_mapping():
    ret = FakeRetrievalGateway(items=[_mk_ev()], status=RAGStatus.degraded)
    gen = FakeGenerationClient(answer="degraded", status=RAGStatus.degraded)
    rag_svc = _make_fake_rag_service(retrieval=ret, generation=gen)
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert result["status"] == "degraded"


def test_rag_error_mapping():
    """Hybrid with facts + RAG error → degraded (safe fallback)."""
    ret = FakeRetrievalGateway(status=RAGStatus.error,
                               error=ErrorItem(code="RETRIEVAL_ERROR",
                               message="f", component="retrieval"))
    rag_svc = _make_fake_rag_service(retrieval=ret)
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert result["status"] == "degraded"
    codes = {w["code"] for w in result["warnings"]}
    assert "GENERATION_DEGRADED" in codes


def test_pure_semantic_no_service_returns_error():
    """Pure rag_query with no service → error."""
    result = _invoke_agent("为什么世界杯比赛很经典？")
    assert result["status"] == "error"
    codes = {w["code"] for w in result["warnings"]}
    assert "DATA_SOURCE_UNAVAILABLE" in codes


# ====================================================================
# 12. evidence not in public response
# ====================================================================
def test_evidence_not_in_response():
    rag_svc, _, _ = _mk_svc()
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert "evidence" not in result


# ====================================================================
# 13. confidence = null
# ====================================================================
def test_confidence_null():
    rag_svc, _, _ = _mk_svc()
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    assert result["confidence"] is None


# ====================================================================
# 14. Mock mode still works
# ====================================================================
def test_mock_mode_still_works():
    from backend.application.mock_agent_service import MockAgentService
    svc = MockAgentService()
    result = svc.query({"question": "2022年世界杯决赛比分是多少？",
                        "session_id": None, "filters": {}}, "trace-x")
    assert result["data_status"] == "mock"
    assert result["status"] == "ok"


# ====================================================================
# 15. Missing API key doesn't break exact query
# ====================================================================
def test_missing_api_key_exact_query_works():
    result = _invoke_agent("2022年世界杯决赛比分是多少？")
    assert result["status"] != "error"


# ====================================================================
# 16. RAG service None returns error for semantic
# ====================================================================
def test_rag_service_none_hybrid_degraded():
    """Hybrid with facts + no RAG service → degraded, facts preserved."""
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节")
    assert result["status"] == "degraded"
    codes = {w["code"] for w in result["warnings"]}
    assert "GENERATION_DEGRADED" in codes
    assert len(result.get("facts", [])) > 0  # facts preserved


# ====================================================================
# 17. Explicit filters preserved
# ====================================================================
def test_explicit_filters_preserved():
    rag_svc, ret, gen = _mk_svc()
    _invoke_agent("介绍2022年世界杯决赛的重要情节",
                  filters={"years": [2022], "stages": ["final"]},
                  rag_service=rag_svc)
    assert ret.last_request is not None
    assert ret.last_request.filters.years == [2022]
    assert ret.last_request.filters.stages == ["final"]


# ====================================================================
# 18. No self-loop graph edges
# ====================================================================
def test_rag_facts_no_self_loop_edges():
    ret = FakeRetrievalGateway(items=[_mk_ev()])
    gen = FakeGenerationClient(
        answer="比赛精彩",
        facts=[MatchResultFact(
            fact_id="f1", match_id="M-2022-64", tournament_year=2022,
            stage="final", stage_name="决赛",
            home_team_id="team_ARG", home_team_name="阿根廷",
            away_team_id="team_FRA", away_team_name="法国",
            score_display="3:3", penalty_score="4:2",
            result_type="penalties", winner_team_id="team_ARG",
            text="阿根廷点球获胜。",
        )],
        sources=[SourceItem(source_id="s1", title="T")],
    )
    rag_svc = _make_fake_rag_service(retrieval=ret, generation=gen)
    result = _invoke_agent("介绍2022年世界杯决赛的重要情节",
                           rag_service=rag_svc)
    edges = result.get("graph", {}).get("edges", [])
    for e in edges:
        assert e["source"] != e["target"], f"Self-loop on {e['id']}"
