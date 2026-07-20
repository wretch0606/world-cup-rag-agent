"""Contract tests for the shared RAG Pydantic models (rag-v1.1-draft).

These tests validate model construction, cross-field validators, enum
completeness, JSON round-trips, and the discriminated fact union.

No real LLM, Chroma, network, or absolute paths are used.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.schemas.common import StageEnum
from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    GenerationMeta,
    MatchResultFact,
    QueryTypeEnum,
    RAGOptions,
    RAGRequest,
    RAGResult,
    RAGTiming,
    RelationFact,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResult,
    SourceItem,
    StructuredFact,
    SummaryFact,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_source_item_dict() -> dict:
    return {
        "source_id": "src-001",
        "title": "FIFA World Cup 2022",
        "url": "https://example.org/world-cup-2022-final",
        "page": None,
        "document_id": "document-001",
        "data_version": "2026-07-16-v1",
        "used_for_fact_ids": ["fact-M-2022-64-result"],
        "source_type": "csv",
        "publisher": "Kaggle (Jahaidul Islam)",
        "retrieved_at": "2026-07-16",
    }


@pytest.fixture
def valid_filters_dict() -> dict:
    return {
        "years": [2022],
        "team_ids": ["team_ARG", "team_FRA"],
        "stages": ["final"],
        "result_types": [],
        "match_ids": ["M-2022-64"],
    }


@pytest.fixture
def valid_rag_request_dict(valid_filters_dict) -> dict:
    return {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "trace-20260716-001",
        "question": "2022年世界杯决赛有哪些重要情节？",
        "original_question": "介绍一下2022年世界杯决赛",
        "query_type": "hybrid",
        "filters": valid_filters_dict,
        "structured_facts": [],
        "source_catalog": [],
        "options": {"retrieval_top_k": 10, "rerank_top_n": 5},
    }


# ---------------------------------------------------------------------------
# 1. StageEnum completeness
# ---------------------------------------------------------------------------
def test_stage_enum_has_8_values():
    expected = {
        "group",
        "second_group",
        "round_of_16",
        "quarter_final",
        "semi_final",
        "third_place",
        "final_round",
        "final",
    }
    actual = {e.value for e in StageEnum}
    assert actual == expected


# ---------------------------------------------------------------------------
# 2. RAGRequest validation
# ---------------------------------------------------------------------------
def test_rag_request_valid(valid_rag_request_dict):
    req = RAGRequest(**valid_rag_request_dict)
    assert req.contract_version == RAG_CONTRACT_VERSION
    assert req.trace_id == "trace-20260716-001"
    assert req.query_type == QueryTypeEnum.hybrid


def test_rag_request_extra_forbid(valid_rag_request_dict):
    data = {**valid_rag_request_dict, "unknown_field": "should_fail"}
    with pytest.raises(ValidationError):
        RAGRequest(**data)


# ---------------------------------------------------------------------------
# 3. RAGOptions: rerank_top_n <= retrieval_top_k
# ---------------------------------------------------------------------------
def test_options_rerank_top_n_exceeds_retrieval_top_k():
    with pytest.raises(ValidationError, match="rerank"):
        RAGOptions(retrieval_top_k=5, rerank_top_n=10)


def test_options_rerank_top_n_valid():
    opts = RAGOptions(retrieval_top_k=10, rerank_top_n=5)
    assert opts.rerank_top_n == 5


def test_options_defaults():
    opts = RAGOptions()
    assert opts.retrieval_top_k == 10
    assert opts.rerank_top_n == 5
    assert opts.timeout_ms == 8000


# ---------------------------------------------------------------------------
# 4. StructuredFact: result_type constraints
# ---------------------------------------------------------------------------
def test_structured_fact_penalties_requires_penalty_score():
    with pytest.raises(ValidationError, match="penalty_score"):
        StructuredFact(
            match_id="M-1",
            tournament_year=2022,
            stage="final",
            stage_name="决赛",
            home_team_id="t1",
            home_team_name="A",
            away_team_id="t2",
            away_team_name="B",
            score_display="3:3",
            result_type="penalties",
            penalty_score=None,
            winner_team_id="t1",
        )


def test_structured_fact_draw_requires_winner_null():
    with pytest.raises(ValidationError, match="winner_team_id"):
        StructuredFact(
            match_id="M-1",
            tournament_year=2022,
            stage="group",
            stage_name="小组赛",
            home_team_id="t1",
            home_team_name="A",
            away_team_id="t2",
            away_team_name="B",
            score_display="1:1",
            result_type="draw",
            winner_team_id="t1",
        )


# ---------------------------------------------------------------------------
# 5. RAGResult: status / error consistency
# ---------------------------------------------------------------------------
def test_rag_result_status_error_requires_error_item(valid_filters_dict):
    with pytest.raises(ValidationError, match="error"):
        RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id="t1",
            status="error",
            answer="...",
            applied_filters=RetrievalFilters(**valid_filters_dict),
            error=None,
        )


def test_rag_result_status_ok_requires_error_null(valid_filters_dict):
    with pytest.raises(ValidationError, match="error"):
        RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id="t1",
            status="ok",
            answer="...",
            applied_filters=RetrievalFilters(**valid_filters_dict),
            error=ErrorItem(code="X", message="...", component="test"),
        )


# ---------------------------------------------------------------------------
# 6. Confidence range
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_value", [-0.1, 1.1, -10, 2.0])
def test_confidence_out_of_range_fails(bad_value, valid_filters_dict):
    with pytest.raises(ValidationError, match="confidence"):
        RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id="t1",
            status="ok",
            answer="...",
            applied_filters=RetrievalFilters(**valid_filters_dict),
            confidence=bad_value,
        )


def test_confidence_null_passes(valid_filters_dict):
    result = RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="t1",
        status="ok",
        answer="...",
        applied_filters=RetrievalFilters(**valid_filters_dict),
        confidence=None,
    )
    assert result.confidence is None


def test_confidence_in_range_passes(valid_filters_dict):
    result = RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="t1",
        status="ok",
        answer="...",
        applied_filters=RetrievalFilters(**valid_filters_dict),
        confidence=0.85,
    )
    assert result.confidence == 0.85


# ---------------------------------------------------------------------------
# 7. SourceItem: old + new fields
# ---------------------------------------------------------------------------
def test_source_item_with_generation_v2_fields(valid_source_item_dict):
    s = SourceItem(**valid_source_item_dict)
    assert s.source_id == "src-001"
    assert s.source_type == "csv"
    assert s.publisher == "Kaggle (Jahaidul Islam)"
    assert s.retrieved_at == "2026-07-16"


def test_source_item_minimal():
    s = SourceItem(source_id="s1", title="T")
    assert s.source_id == "s1"
    assert s.source_type is None
    assert s.publisher is None
    assert s.retrieved_at is None
    assert s.used_for_fact_ids == []


def test_source_item_extra_forbid(valid_source_item_dict):
    data = {**valid_source_item_dict, "bogus": 42}
    with pytest.raises(ValidationError):
        SourceItem(**data)


# ---------------------------------------------------------------------------
# 8. JSON round-trip
# ---------------------------------------------------------------------------
def test_rag_result_json_round_trip(valid_filters_dict):
    """Full RAGResult survives model_dump_json → model_validate_json."""
    result = RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="trace-rtt-001",
        status="ok",
        answer="阿根廷在点球大战中以4:2获胜。",
        facts=[
            MatchResultFact(
                fact_id="fact-1",
                match_id="M-2022-64",
                tournament_year=2022,
                stage="final",
                stage_name="决赛",
                home_team_id="team_ARG",
                home_team_name="阿根廷",
                away_team_id="team_FRA",
                away_team_name="法国",
                score_display="3:3",
                penalty_score="4:2",
                result_type="penalties",
                winner_team_id="team_ARG",
                text="阿根廷点球获胜。",
                source_ids=["src-001"],
            )
        ],
        sources=[
            SourceItem(
                source_id="src-001",
                title="FIFA Dataset",
                source_type="csv",
                publisher="Kaggle",
                retrieved_at="2026-07-16",
                used_for_fact_ids=["fact-1"],
            )
        ],
        evidence=[],
        applied_filters=RetrievalFilters(**valid_filters_dict),
        confidence=None,
        timing=RAGTiming(generation_ms=420, total_ms=620),
        generation_meta=GenerationMeta(prompt_name="summary"),
    )

    json_str = result.model_dump_json()
    assert isinstance(json_str, str)

    # Must parse as valid JSON
    parsed = json.loads(json_str)
    assert parsed["contract_version"] == RAG_CONTRACT_VERSION
    assert parsed["trace_id"] == "trace-rtt-001"
    assert parsed["status"] == "ok"
    assert len(parsed["facts"]) == 1
    assert parsed["facts"][0]["fact_type"] == "match_result"

    # Round-trip back to model
    reloaded = RAGResult.model_validate_json(json_str)
    assert reloaded.trace_id == result.trace_id
    assert reloaded.status == result.status
    assert reloaded.answer == result.answer
    assert len(reloaded.facts) == 1


# ---------------------------------------------------------------------------
# 9. Contract version
# ---------------------------------------------------------------------------
def test_contract_version_is_rag_v1_1_draft():
    assert RAG_CONTRACT_VERSION == "rag-v1.1-draft"


# ---------------------------------------------------------------------------
# 10. Fact discriminator
# ---------------------------------------------------------------------------
def test_fact_discriminator_match_result():
    fact = MatchResultFact(
        fact_id="f1",
        match_id="M-1",
        tournament_year=2022,
        stage="final",
        stage_name="决赛",
        home_team_id="t1",
        home_team_name="A",
        away_team_id="t2",
        away_team_name="B",
        score_display="1:0",
        result_type="regulation",
        winner_team_id="t1",
        text="A 1:0 B",
    )
    assert fact.fact_type == "match_result"
    d = fact.model_dump()
    assert d["fact_type"] == "match_result"


def test_fact_discriminator_relation():
    fact = RelationFact(
        fact_id="f2",
        team_ids=["team_ARG"],
        match_ids=["M-1"],
        text="阿根廷对阵...",
    )
    assert fact.fact_type == "relation"


def test_fact_discriminator_summary():
    fact = SummaryFact(
        fact_id="f3",
        match_ids=["M-1", "M-2"],
        tournament_years=[2022],
        text="总结...",
    )
    assert fact.fact_type == "summary"


def test_fact_union_deserializes_match_result(valid_filters_dict):
    """RAGResult with a match_result fact deserializes to MatchResultFact."""
    data = {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "t1",
        "status": "ok",
        "answer": "test",
        "applied_filters": {"years": [2022]},
        "facts": [
            {
                "fact_type": "match_result",
                "fact_id": "f1",
                "match_id": "M-1",
                "tournament_year": 2022,
                "stage": "final",
                "stage_name": "决赛",
                "home_team_id": "t1",
                "home_team_name": "A",
                "away_team_id": "t2",
                "away_team_name": "B",
                "score_display": "1:0",
                "result_type": "regulation",
                "winner_team_id": "t1",
                "text": "...",
            }
        ],
    }
    result = RAGResult(**data)
    assert len(result.facts) == 1
    assert isinstance(result.facts[0], MatchResultFact)


# ---------------------------------------------------------------------------
# 11. RetrievalFilters vs MatchFilters (distinct models)
# ---------------------------------------------------------------------------
def test_retrieval_filters_has_match_ids():
    rf = RetrievalFilters(match_ids=["M-1"])
    assert rf.match_ids == ["M-1"]


def test_retrieval_filters_defaults():
    rf = RetrievalFilters()
    assert rf.years == []
    assert rf.team_ids == []
    assert rf.stages == []
    assert rf.result_types == []
    assert rf.match_ids == []


# ---------------------------------------------------------------------------
# 12. Default arrays are empty lists, not None
# ---------------------------------------------------------------------------
def test_default_arrays_are_empty_lists():
    rf = RetrievalFilters()
    assert rf.years == []
    assert isinstance(rf.years, list)

    result = RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="t1",
        status="ok",
        answer="...",
        applied_filters=RetrievalFilters(),
    )
    assert result.facts == []
    assert result.sources == []
    assert result.evidence == []
    assert result.warnings == []


# ---------------------------------------------------------------------------
# 13. RetrievalRequest / RetrievalResult
# ---------------------------------------------------------------------------
def test_retrieval_request_round_trip():
    req = RetrievalRequest(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="t1",
        query="test query",
        original_question="test?",
        filters=RetrievalFilters(years=[2022]),
        options=RAGOptions(),
    )
    assert req.query == "test query"


def test_retrieval_result_status_error_consistency():
    """RetrievalResult also enforces status/error consistency."""
    with pytest.raises(ValidationError, match="error"):
        RetrievalResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id="t1",
            status="error",
            original_query="q",
            applied_filters=RetrievalFilters(),
            error=None,
        )


# ---------------------------------------------------------------------------
# 14. ErrorItem
# ---------------------------------------------------------------------------
def test_error_item_minimal():
    e = ErrorItem(code="TIMEOUT", message="超时", component="retrieval")
    assert e.code == "TIMEOUT"
    assert e.detail_id is None


def test_error_item_with_detail():
    e = ErrorItem(
        code="INTERNAL_ERROR",
        message="内部错误",
        component="rag_service",
        detail_id="err-001",
    )
    assert e.detail_id == "err-001"
