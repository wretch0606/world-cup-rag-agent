"""Deterministic, evidence-backed answer generation for the offline demo.

This client never invents facts and never calls a model. It formats trusted
SQLite facts and Chroma evidence into a useful degraded response so the full
demo can run without an API key.
"""

from __future__ import annotations

import time

from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    EvidenceItem,
    GenerationMeta,
    MatchResultFact,
    RAGRequest,
    RAGResult,
    RAGStatus,
    RAGTiming,
    RetrievalResult,
    SourceItem,
    StructuredFact,
    SummaryFact,
    WarningItem,
)


class OfflineEvidenceGenerationClient:
    """Format only trusted request facts and retrieval evidence."""

    async def generate(self, request: RAGRequest, retrieval: RetrievalResult) -> RAGResult:
        started = time.monotonic()

        if retrieval.status == RAGStatus.error:
            return _error_result(request, retrieval, started)

        if not request.structured_facts and not retrieval.items:
            return _empty_result(request, retrieval, started)

        facts = [_match_fact(fact) for fact in request.structured_facts]
        if facts:
            answer = _structured_answer(request.structured_facts, retrieval.items)
        else:
            summary = _summary_fact(retrieval.items)
            facts = [summary]
            answer = summary.text

        sources = _trusted_sources(request, retrieval.items, facts)
        return RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            status=RAGStatus.degraded,
            answer=answer,
            facts=facts,
            sources=sources,
            evidence=list(retrieval.items),
            applied_filters=retrieval.applied_filters,
            confidence=None,
            rewrite_applied=retrieval.rewrite_applied,
            rerank_applied=retrieval.rerank_applied,
            warnings=[
                WarningItem(
                    code="OFFLINE_GENERATION",
                    message="未调用大模型；当前答案仅整理 SQLite 事实与 Chroma 检索证据。",
                    component="generation",
                    retryable=False,
                )
            ],
            timing=RAGTiming(
                rewrite_ms=retrieval.timing.rewrite_ms,
                retrieval_ms=retrieval.timing.retrieval_ms,
                rerank_ms=retrieval.timing.rerank_ms,
                generation_ms=_elapsed_ms(started),
                total_ms=retrieval.timing.total_ms + _elapsed_ms(started),
            ),
            generation_meta=GenerationMeta(
                prompt_name="offline_evidence",
                prompt_version="offline-evidence-v1.0",
                model_name="deterministic-template",
            ),
            error=None,
        )


def _match_fact(fact: StructuredFact) -> MatchResultFact:
    return MatchResultFact(
        fact_id=f"fact-{fact.match_id}-offline",
        match_id=fact.match_id,
        tournament_year=fact.tournament_year,
        stage=fact.stage,
        stage_name=fact.stage_name,
        home_team_id=fact.home_team_id,
        home_team_name=fact.home_team_name,
        away_team_id=fact.away_team_id,
        away_team_name=fact.away_team_name,
        home_score_90=fact.home_score_90,
        away_score_90=fact.away_score_90,
        home_score_et=fact.home_score_et,
        away_score_et=fact.away_score_et,
        home_penalties=fact.home_penalties,
        away_penalties=fact.away_penalties,
        score_display=fact.score_display,
        penalty_score=fact.penalty_score,
        result_type=fact.result_type,
        winner_team_id=fact.winner_team_id,
        text=_format_match(fact),
        source_ids=list(fact.source_ids),
    )


def _format_match(fact: StructuredFact) -> str:
    parts = [
        f"{fact.tournament_year}年世界杯{fact.stage_name}",
        f"{fact.home_team_name}对阵{fact.away_team_name}",
    ]
    if fact.home_score_90 is not None and fact.away_score_90 is not None:
        parts.append(f"90分钟比分{fact.home_score_90}:{fact.away_score_90}")
    if fact.home_score_et is not None and fact.away_score_et is not None:
        parts.append(f"加时赛后{fact.home_score_et}:{fact.away_score_et}")
    elif fact.score_display:
        parts.append(f"正式比分{fact.score_display}")
    if fact.penalty_score:
        parts.append(f"点球大战{fact.penalty_score}")

    winner_name = _winner_name(fact)
    if winner_name:
        parts.append(f"{winner_name}获胜")
    return "，".join(parts) + "。"


def _winner_name(fact: StructuredFact) -> str:
    if fact.winner_team_id == fact.home_team_id:
        return fact.home_team_name
    if fact.winner_team_id == fact.away_team_id:
        return fact.away_team_name
    return ""


def _structured_answer(
    structured_facts: list[StructuredFact],
    evidence: list[EvidenceItem],
) -> str:
    fact_text = " ".join(_format_match(fact) for fact in structured_facts[:3])
    excerpts = _evidence_excerpts(evidence)
    if not excerpts:
        return fact_text

    new_excerpts = [excerpt for excerpt in excerpts if excerpt not in fact_text]
    if not new_excerpts:
        return fact_text
    return f"{fact_text} 检索证据：{'；'.join(new_excerpts)}"


def _summary_fact(evidence: list[EvidenceItem]) -> SummaryFact:
    excerpts = _evidence_excerpts(evidence)
    source_ids = list(dict.fromkeys(item.source_id for item in evidence if item.source_id))
    match_ids = list(dict.fromkeys(item.match_id for item in evidence if item.match_id))
    text = "根据知识库检索到的资料：" + "；".join(excerpts)
    return SummaryFact(
        fact_id="fact-offline-evidence-summary",
        match_ids=match_ids,
        tournament_years=[],
        text=text,
        source_ids=source_ids,
    )


def _evidence_excerpts(evidence: list[EvidenceItem]) -> list[str]:
    excerpts: list[str] = []
    for item in evidence:
        text = " ".join(item.text.split()).strip()
        if not text:
            continue
        if len(text) > 220:
            text = text[:217].rstrip() + "..."
        if text not in excerpts:
            excerpts.append(text)
        if len(excerpts) == 3:
            break
    return excerpts


def _trusted_sources(
    request: RAGRequest,
    evidence: list[EvidenceItem],
    facts: list[MatchResultFact | SummaryFact],
) -> list[SourceItem]:
    sources_by_id = {source.source_id: source for source in request.source_catalog}
    for item in evidence:
        if not item.source_id or item.source_id in sources_by_id:
            continue
        sources_by_id[item.source_id] = SourceItem(
            source_id=item.source_id,
            title=item.document_name,
            url=item.source_url,
            page=item.source_page,
            document_id=item.document_id,
            data_version=item.data_version,
        )

    fact_ids_by_source: dict[str, list[str]] = {}
    for fact in facts:
        for source_id in fact.source_ids:
            fact_ids_by_source.setdefault(source_id, []).append(fact.fact_id)

    return [
        source.model_copy(update={"used_for_fact_ids": fact_ids_by_source[source_id]})
        for source_id, source in sources_by_id.items()
        if source_id in fact_ids_by_source
    ]


def _empty_result(
    request: RAGRequest,
    retrieval: RetrievalResult,
    started: float,
) -> RAGResult:
    return RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id=request.trace_id,
        status=RAGStatus.empty,
        answer="未找到与您的问题相关的可靠信息。",
        facts=[],
        sources=[],
        evidence=[],
        applied_filters=retrieval.applied_filters,
        warnings=[
            WarningItem(
                code="NO_RESULT",
                message="没有找到可靠的事实或证据。",
                component="retrieval",
                retryable=False,
            )
        ],
        timing=RAGTiming(generation_ms=_elapsed_ms(started)),
        generation_meta=GenerationMeta(prompt_name="offline_evidence"),
        error=None,
    )


def _error_result(
    request: RAGRequest,
    retrieval: RetrievalResult,
    started: float,
) -> RAGResult:
    return RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id=request.trace_id,
        status=RAGStatus.error,
        answer="知识库检索失败，无法整理离线答案。",
        facts=[],
        sources=[],
        evidence=[],
        applied_filters=retrieval.applied_filters,
        timing=RAGTiming(generation_ms=_elapsed_ms(started)),
        generation_meta=GenerationMeta(prompt_name="offline_evidence"),
        error=retrieval.error
        or ErrorItem(
            code="RETRIEVAL_ERROR",
            message="检索失败，无法生成答案。",
            component="retrieval",
            retryable=True,
        ),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
