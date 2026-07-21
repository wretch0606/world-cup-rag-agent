"""Service boundary tests for RagService.generate.

Uses Fake implementations of RetrievalGateway and GenerationClient —
never real LLM, Chroma, or network calls.

Async tests use ``asyncio.run()`` (no pytest-asyncio dependency).
"""

from __future__ import annotations

import asyncio
import inspect

from backend.rag.service import RagService
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
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTiming,
    SourceItem,
    WarningItem,
)


# ---------------------------------------------------------------------------
# Fake implementations
# ---------------------------------------------------------------------------
class FakeRetrievalGateway:
    """Deterministic fake for RetrievalGateway protocol."""

    def __init__(
        self,
        *,
        items: list[EvidenceItem] | None = None,
        status: RAGStatus = RAGStatus.ok,
        warnings: list[WarningItem] | None = None,
        error: ErrorItem | None = None,
        rewritten_queries: list[str] | None = None,
        rewrite_applied: bool = False,
        rerank_applied: bool = False,
        timing: RetrievalTiming | None = None,
        should_raise: BaseException | None = None,
    ):
        self.items = items or []
        self.status = status
        self._warnings = warnings or []
        self._error = error
        self._rewritten = rewritten_queries or []
        self._rewrite_applied = rewrite_applied
        self._rerank_applied = rerank_applied
        self._timing = timing or RetrievalTiming()
        self.should_raise = should_raise
        self.last_request: RetrievalRequest | None = None

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.last_request = request
        if self.should_raise is not None:
            raise self.should_raise
        return RetrievalResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            status=self.status,
            original_query=request.query,
            rewritten_queries=self._rewritten,
            items=self.items,
            applied_filters=request.filters,
            rewrite_applied=self._rewrite_applied,
            rerank_applied=self._rerank_applied,
            warnings=self._warnings,
            timing=self._timing,
            error=self._error,
        )


class FakeGenerationClient:
    """Deterministic fake for GenerationClient protocol."""

    def __init__(
        self,
        *,
        answer: str = "这是一个测试回答。",
        facts: list | None = None,
        sources: list[SourceItem] | None = None,
        confidence: float | None = None,
        warnings: list[WarningItem] | None = None,
        generation_meta: GenerationMeta | None = None,
        status: RAGStatus = RAGStatus.ok,
        should_raise: BaseException | None = None,
    ):
        self.answer = answer
        self._facts = facts or []
        self._sources = sources or []
        self._confidence = confidence
        self._warnings = warnings or []
        self._generation_meta = generation_meta or GenerationMeta()
        self._status = status
        self.should_raise = should_raise

    async def generate(self, request: RAGRequest, retrieval: RetrievalResult) -> RAGResult:
        if self.should_raise is not None:
            raise self.should_raise
        return RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            status=self._status,
            answer=self.answer,
            facts=self._facts,
            sources=self._sources,
            evidence=retrieval.items,
            applied_filters=retrieval.applied_filters,
            confidence=self._confidence,
            rewrite_applied=retrieval.rewrite_applied,
            rerank_applied=retrieval.rerank_applied,
            warnings=self._warnings,
            timing=RAGTiming(generation_ms=100, total_ms=500),
            generation_meta=self._generation_meta,
            error=None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_request(**overrides) -> RAGRequest:
    kwargs = {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "trace-test-001",
        "question": "测试问题",
        "original_question": "测试问题",
        "query_type": "semantic",
        "filters": RetrievalFilters(years=[2022]),
        "structured_facts": [],
        "source_catalog": [],
        "options": {},
    }
    kwargs.update(overrides)
    return RAGRequest(**kwargs)


def _make_evidence(chunk_id: str = "chunk-001") -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id="doc-001",
        source_id="src-001",
        document_name="Test Document",
        text="检索到的测试文本片段。",
        data_version="2026-07-v1",
        language="zh",
    )


def _run(coro):
    """Run an async coroutine synchronously via asyncio.run()."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. Async entry point
# ---------------------------------------------------------------------------
def test_rag_service_generate_is_async_entry():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert isinstance(result, RAGResult)
        assert result.status == RAGStatus.ok

    _run(_test())


# ---------------------------------------------------------------------------
# 2. B does not directly depend on D
# ---------------------------------------------------------------------------
def test_b_does_not_directly_depend_on_d():
    """RagService.__init__ accepts RetrievalGateway protocol, not D impl."""
    sig = inspect.signature(RagService.__init__)
    params = list(sig.parameters.values())
    retrieval_param = params[1]  # 'retrieval' (first after 'self')
    assert retrieval_param.name == "retrieval"

    # Must not import any concrete D module
    import backend.rag.service as svc_mod

    source = inspect.getsource(svc_mod)
    assert "chroma_service" not in source, "RagService must not import chroma_service"


# ---------------------------------------------------------------------------
# 3. trace_id passthrough
# ---------------------------------------------------------------------------
def test_trace_id_passthrough():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request(trace_id="my-trace-42"))
        assert result.trace_id == "my-trace-42"

    _run(_test())


# ---------------------------------------------------------------------------
# 4. Normal result flow
# ---------------------------------------------------------------------------
def test_normal_result_flow():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(
                items=[_make_evidence()],
                rewrite_applied=True,
                rerank_applied=True,
            ),
            generation=FakeGenerationClient(
                answer="正常回答内容。",
                sources=[
                    SourceItem(
                        source_id="src-001",
                        title="Test Source",
                        source_type="csv",
                    )
                ],
            ),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.ok
        assert result.answer == "正常回答内容。"
        assert len(result.evidence) == 1
        assert len(result.sources) == 1
        assert result.rewrite_applied is True
        assert result.rerank_applied is True
        assert result.timing.total_ms >= 0
        assert result.error is None

    _run(_test())


# ---------------------------------------------------------------------------
# 5. Empty retrieval
# ---------------------------------------------------------------------------
def test_empty_retrieval():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[], status=RAGStatus.empty),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.empty
        assert result.facts == []
        assert result.sources == []
        assert result.evidence == []
        warning_codes = {w.code for w in result.warnings}
        assert "NO_RESULT" in warning_codes

    _run(_test())


# ---------------------------------------------------------------------------
# 6. Retrieval degraded
# ---------------------------------------------------------------------------
def test_retrieval_degraded():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(
                items=[_make_evidence()],
                status=RAGStatus.degraded,
                warnings=[
                    WarningItem(
                        code="QUERY_REWRITE_UNAVAILABLE",
                        message="查询改写不可用",
                        component="retrieval",
                    )
                ],
            ),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.degraded
        assert result.rewrite_applied is False
        codes = {w.code for w in result.warnings}
        assert "QUERY_REWRITE_UNAVAILABLE" in codes

    _run(_test())


# ---------------------------------------------------------------------------
# 7. Retrieval error (gateway returns error status)
# ---------------------------------------------------------------------------
def test_retrieval_error_status():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(
                status=RAGStatus.error,
                error=ErrorItem(
                    code="RETRIEVAL_ERROR",
                    message="Chroma 连接失败",
                    component="retrieval",
                    retryable=True,
                ),
            ),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error
        assert result.error is not None
        assert result.error.code == "RETRIEVAL_ERROR"

    _run(_test())


# ---------------------------------------------------------------------------
# 8. Retrieval gateway raises exception
# ---------------------------------------------------------------------------
def test_retrieval_gateway_raises():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(should_raise=RuntimeError("boom")),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error
        assert result.error is not None
        assert result.error.code == "RETRIEVAL_ERROR"
        assert "暂时不可用" in result.error.message

    _run(_test())


# ---------------------------------------------------------------------------
# 9. Generation error
# ---------------------------------------------------------------------------
def test_generation_error():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(should_raise=RuntimeError("llm down")),
        )
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error
        assert result.error is not None
        assert result.error.code == "GENERATION_ERROR"

    _run(_test())


# ---------------------------------------------------------------------------
# 10. Service unconfigured
# ---------------------------------------------------------------------------
def test_service_unconfigured_returns_error():
    async def _test():
        svc = RagService(retrieval=None, generation=None)
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error
        assert result.error is not None
        assert result.error.code == "INTERNAL_ERROR"
        assert "未配置" in result.error.message

    _run(_test())


def test_service_missing_retrieval_returns_error():
    async def _test():
        svc = RagService(retrieval=None, generation=FakeGenerationClient())
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error

    _run(_test())


def test_service_missing_generation_returns_error():
    async def _test():
        svc = RagService(retrieval=FakeRetrievalGateway(), generation=None)
        result = await svc.generate(_make_request())
        assert result.status == RAGStatus.error

    _run(_test())


# ---------------------------------------------------------------------------
# 11. No fabricated sources
# ---------------------------------------------------------------------------
def test_no_fabricated_sources():
    """SourceItem used_for_fact_ids must reference real fact_ids."""

    async def _test():
        fact = MatchResultFact(
            fact_id="fact-real-001",
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
            text="A 胜 B",
            source_ids=["src-real-001"],
        )
        source = SourceItem(
            source_id="src-real-001",
            title="Real Source",
            used_for_fact_ids=["fact-real-001"],
        )
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(
                answer="回答",
                facts=[fact],
                sources=[source],
            ),
        )
        result = await svc.generate(_make_request())
        assert len(result.sources) == 1

        fact_ids = {f.fact_id for f in result.facts}
        for s in result.sources:
            for fid in s.used_for_fact_ids:
                assert fid in fact_ids, f"Source references unknown fact_id: {fid}"

    _run(_test())


# ---------------------------------------------------------------------------
# 12. Contract version in result
# ---------------------------------------------------------------------------
def test_contract_version_in_result():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.contract_version == RAG_CONTRACT_VERSION

    _run(_test())


# ---------------------------------------------------------------------------
# 13. Timing fields non-negative
# ---------------------------------------------------------------------------
def test_timing_fields_non_negative():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(),
        )
        result = await svc.generate(_make_request())
        assert result.timing.total_ms >= 0
        assert result.timing.generation_ms >= 0
        assert result.timing.retrieval_ms >= 0

    _run(_test())


# ---------------------------------------------------------------------------
# 14. Retrieval filters pass through to gateway
# ---------------------------------------------------------------------------
def test_retrieval_filters_passed_through():
    async def _test():
        fake_retrieval = FakeRetrievalGateway(items=[_make_evidence()])
        svc = RagService(
            retrieval=fake_retrieval,
            generation=FakeGenerationClient(),
        )
        request = _make_request(
            filters=RetrievalFilters(years=[2018, 2022], stages=["final"]),
        )
        await svc.generate(request)
        assert fake_retrieval.last_request is not None
        assert fake_retrieval.last_request.filters.years == [2018, 2022]
        assert fake_retrieval.last_request.filters.stages == ["final"]

    _run(_test())


# ---------------------------------------------------------------------------
# 15. Confidence null when not provided
# ---------------------------------------------------------------------------
def test_confidence_null_when_not_provided():
    async def _test():
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(confidence=None),
        )
        result = await svc.generate(_make_request())
        assert result.confidence is None

    _run(_test())


# ---------------------------------------------------------------------------
# 16. Generation meta passthrough
# ---------------------------------------------------------------------------
def test_generation_meta_passthrough():
    async def _test():
        meta = GenerationMeta(
            prompt_name="exact_match",
            prompt_version="exact-match-v1.0",
            model_name="test-model",
            confidence_method=None,
        )
        svc = RagService(
            retrieval=FakeRetrievalGateway(items=[_make_evidence()]),
            generation=FakeGenerationClient(generation_meta=meta),
        )
        result = await svc.generate(_make_request())
        assert result.generation_meta.prompt_name == "exact_match"
        assert result.generation_meta.prompt_version == "exact-match-v1.0"
        assert result.generation_meta.model_name == "test-model"

    _run(_test())
