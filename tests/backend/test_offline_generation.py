"""Tests for deterministic, evidence-backed offline generation."""

from __future__ import annotations

import asyncio

from backend.rag.offline_generation import OfflineEvidenceGenerationClient
from backend.rag.protocols import GenerationClient
from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    EvidenceItem,
    MatchResultFact,
    RAGRequest,
    RAGStatus,
    RetrievalFilters,
    RetrievalResult,
    SourceItem,
    StructuredFact,
    SummaryFact,
)


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        chunk_id="match_fact_M-2022-001_v1",
        document_id="match_fact_M-2022-001_v1",
        match_id="M-2022-001",
        source_id="source-demo",
        document_name="FIFA World Cup 2022",
        text="阿根廷与法国在决赛中战成3:3，随后阿根廷赢得点球大战。",
        data_version="demo-v1",
    )


def _request(*, structured: bool = True) -> RAGRequest:
    facts = []
    sources = []
    if structured:
        facts = [
            StructuredFact(
                match_id="M-2022-001",
                tournament_year=2022,
                stage="final",
                stage_name="决赛",
                home_team_id="team_ARG",
                home_team_name="阿根廷",
                away_team_id="team_FRA",
                away_team_name="法国",
                home_score_90=2,
                away_score_90=2,
                home_score_et=3,
                away_score_et=3,
                home_penalties=4,
                away_penalties=2,
                score_display="3:3",
                penalty_score="4:2",
                result_type="penalties",
                winner_team_id="team_ARG",
                source_ids=["source-demo"],
            )
        ]
        sources = [SourceItem(source_id="source-demo", title="FIFA World Cup 2022")]

    return RAGRequest(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="offline-test",
        question="介绍2022年世界杯决赛",
        original_question="介绍2022年世界杯决赛",
        query_type="hybrid" if structured else "semantic",
        filters=RetrievalFilters(years=[2022] if structured else []),
        structured_facts=facts,
        source_catalog=sources,
        options={},
    )


def _retrieval(*, items: list[EvidenceItem] | None = None) -> RetrievalResult:
    return RetrievalResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id="offline-test",
        status=RAGStatus.ok if items else RAGStatus.empty,
        original_query="介绍2022年世界杯决赛",
        items=items or [],
        applied_filters=RetrievalFilters(),
    )


def test_offline_client_satisfies_generation_protocol() -> None:
    assert isinstance(OfflineEvidenceGenerationClient(), GenerationClient)


def test_offline_hybrid_uses_trusted_scores_and_sources() -> None:
    result = asyncio.run(
        OfflineEvidenceGenerationClient().generate(_request(), _retrieval(items=[_evidence()]))
    )

    assert result.status == RAGStatus.degraded
    assert "90分钟比分2:2" in result.answer
    assert "点球大战4:2" in result.answer
    assert {warning.code for warning in result.warnings} == {"OFFLINE_GENERATION"}
    assert result.generation_meta.model_name == "deterministic-template"

    fact = result.facts[0]
    assert isinstance(fact, MatchResultFact)
    assert fact.home_score_90 == 2
    assert fact.home_score_et == 3
    assert fact.home_penalties == 4
    assert result.sources[0].source_id == "source-demo"
    assert result.sources[0].used_for_fact_ids == [fact.fact_id]


def test_offline_semantic_builds_summary_only_from_evidence() -> None:
    result = asyncio.run(
        OfflineEvidenceGenerationClient().generate(
            _request(structured=False),
            _retrieval(items=[_evidence()]),
        )
    )

    assert result.status == RAGStatus.degraded
    assert result.answer.startswith("根据知识库检索到的资料：")
    assert "阿根廷与法国" in result.answer
    assert len(result.facts) == 1
    assert isinstance(result.facts[0], SummaryFact)
    assert result.facts[0].match_ids == ["M-2022-001"]
    assert result.sources[0].document_id == "match_fact_M-2022-001_v1"


def test_offline_generation_returns_empty_without_facts_or_evidence() -> None:
    result = asyncio.run(
        OfflineEvidenceGenerationClient().generate(
            _request(structured=False),
            _retrieval(items=[]),
        )
    )

    assert result.status == RAGStatus.empty
    assert result.facts == []
    assert result.sources == []
    assert {warning.code for warning in result.warnings} == {"NO_RESULT"}
