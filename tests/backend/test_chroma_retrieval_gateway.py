"""Tests for ChromaRetrievalGateway — adapts D sync functions to async protocol.

All tests use injected fake synchronous D callables.  No real Chroma, BGE,
Reranker, network, or absolute paths.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable

from backend.rag.chroma_gateway import (
    ChromaRetrievalGateway,
    _build_filter_dicts,
    _deduplicate_by_chunk_id,
    _map_to_evidence,
    _post_filter_raw,
    _sort_items,
)
from backend.rag.protocols import RetrievalGateway
from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    EvidenceItem,
    RAGOptions,
    RAGStatus,
    RetrievalFilters,
    RetrievalRequest,
)

# ====================================================================
# Shared helpers
# ====================================================================
_required_meta = {
    "source_id": "s",
    "document_id": "d",
    "document_name": "dn",
    "data_version": "v1",
}


# ====================================================================
# Fake D helpers
# ====================================================================
def _fake_d_item(
    chunk_id: str = "chunk-1",
    distance: float = 0.2,
    metadata: dict | None = None,
    rerank_score: float | None = None,
    document: str = "",
) -> dict:
    return {
        "id": chunk_id,
        "document": document or f"Text for {chunk_id}",
        "metadata": metadata
        or {
            "document_id": "doc-1",
            "source_id": "src-1",
            "document_name": "Test Document",
            "data_version": "2026-07-v1",
            "match_id": "M-1",
            "tournament_year": 2022,
            "stage": "final",
            "result_type": "regulation",
        },
        "distance": distance,
        "similarity": round(1 - distance, 4),
        "collection": "world_cup_match_facts",
        "rerank_score": rerank_score,
    }


def _fake_top_k(
    captured: list[dict] | None = None,
    items: list[dict] | None = None,
    should_raise: BaseException | None = None,
) -> Callable:
    """Return a fake query_top_k that records its call args."""

    def fn(query_text, k, collection, filters, use_query_rewrite):
        if captured is not None:
            captured.append(
                {
                    "query_text": query_text,
                    "k": k,
                    "collection": collection,
                    "filters": filters,
                    "use_query_rewrite": use_query_rewrite,
                }
            )
        if should_raise:
            raise should_raise
        return items or []

    return fn


def _fake_rerank(
    captured: list[dict] | None = None,
    items: list[dict] | None = None,
    should_raise: BaseException | None = None,
) -> Callable:
    """Return a fake query_with_rerank that records its call args."""

    def fn(query_text, k, collection, filters, recall_k):
        if captured is not None:
            captured.append(
                {
                    "query_text": query_text,
                    "k": k,
                    "collection": collection,
                    "filters": filters,
                    "recall_k": recall_k,
                }
            )
        if should_raise:
            raise should_raise
        return items or []

    return fn


def _make_request(**overrides) -> RetrievalRequest:
    kwargs = {
        "contract_version": RAG_CONTRACT_VERSION,
        "trace_id": "trace-test-001",
        "query": "测试查询",
        "original_question": "原始问题",
        "filters": RetrievalFilters(),
        "options": RAGOptions(),
    }
    kwargs.update(overrides)
    return RetrievalRequest(**kwargs)


# ====================================================================
# Helpers for async tests
# ====================================================================
def _run(coro):
    return asyncio.run(coro)


# ====================================================================
# 1. Module import does not load D
# ====================================================================
def test_module_import_does_not_load_d():
    """Importing chroma_gateway must not import chroma_service."""
    if "backend.services.chroma_service" in sys.modules:
        # Already loaded by another test — not an error for this test
        return
    import backend.rag.chroma_gateway  # noqa: F401

    assert "backend.services.chroma_service" not in sys.modules


# ====================================================================
# 2. Implements RetrievalGateway protocol
# ====================================================================
def test_implements_retrieval_gateway():
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(),
        query_with_rerank_fn=_fake_rerank(),
    )
    assert isinstance(gw, RetrievalGateway)


# ====================================================================
# 3. query_top_k called with correct params
# ====================================================================
def test_query_top_k_called_with_correct_params():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                query="2022年决赛",
                options=RAGOptions(
                    retrieval_top_k=10,
                    rerank_top_n=5,
                    use_query_rewrite=False,
                    use_reranker=False,
                ),
            )
        )

    result = _run(_test())
    assert result.status == RAGStatus.empty  # no items in fake
    assert len(captured) == 1
    call = captured[0]
    assert call["query_text"] == "2022年决赛"
    assert call["k"] == 10  # retrieval_top_k
    assert call["collection"] == "world_cup_match_facts"
    assert call["use_query_rewrite"] is False


# ====================================================================
# 4. query_with_rerank called with correct params
# ====================================================================
def test_query_with_rerank_called_with_correct_params():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(),
        query_with_rerank_fn=_fake_rerank(captured=captured),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                query="test",
                options=RAGOptions(
                    retrieval_top_k=20,
                    rerank_top_n=5,
                    use_query_rewrite=True,
                    use_reranker=True,
                ),
            )
        )

    _run(_test())
    assert len(captured) == 1
    call = captured[0]
    assert call["query_text"] == "test"
    assert call["k"] == 5  # rerank_top_n
    assert call["recall_k"] == 20  # retrieval_top_k


# ====================================================================
# 5. asyncio.to_thread path
# ====================================================================
def test_asyncio_to_thread_path():
    """D callable is invoked — verifies the async path works."""
    captured: list[dict] = []

    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item()]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.status == RAGStatus.ok
    assert len(captured) == 1  # D was called


# ====================================================================
# 6. Timeout
# ====================================================================
def test_timeout():
    """Low timeout with a slow fake should return TIMEOUT error."""

    def slow_fn(*args, **kwargs):
        import time

        time.sleep(10)
        return []

    gw = ChromaRetrievalGateway(
        query_top_k_fn=slow_fn,
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(options=RAGOptions(timeout_ms=1000))
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert result.error.code == "TIMEOUT"
    assert result.error.retryable is True


# ====================================================================
# 7. D exception
# ====================================================================
def test_d_exception():
    """When D raises, the gateway maps to RETRIEVAL_ERROR."""
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(should_raise=RuntimeError("Chroma down")),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert result.error.code == "RETRIEVAL_ERROR"


# ====================================================================
# 8. Empty result
# ====================================================================
def test_empty_result():
    """D returns no candidates → status=empty with NO_RESULT warning."""
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(items=[]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.status == RAGStatus.empty
    assert result.items == []
    codes = {w.code for w in result.warnings}
    assert "NO_RESULT" in codes


# ====================================================================
# 9. Single year mapping
# ====================================================================
def test_single_year_mapping():
    """years=[2022] should produce tournament_year=2022 in filter."""
    dicts, warnings = _build_filter_dicts(
        RetrievalFilters(years=[2022])
    )
    assert len(dicts) == 1
    assert dicts[0] == {"tournament_year": 2022}
    assert warnings == []


# ====================================================================
# 10. Single team mapping
# ====================================================================
def test_single_team_mapping():
    dicts, _ = _build_filter_dicts(RetrievalFilters(team_ids=["team_ARG"]))
    assert dicts == [{"team_id": "team_ARG"}]


# ====================================================================
# 11. Single stage mapping
# ====================================================================
def test_single_stage_mapping():
    dicts, _ = _build_filter_dicts(RetrievalFilters(stages=["final"]))
    assert dicts == [{"stage_enum": "final"}]


# ====================================================================
# 12. Multi-value combination
# ====================================================================
def test_multi_value_combination():
    """years=[2018, 2022] → two filter dicts."""
    dicts, _ = _build_filter_dicts(
        RetrievalFilters(years=[2018, 2022])
    )
    assert len(dicts) == 2
    assert {"tournament_year": 2018} in dicts
    assert {"tournament_year": 2022} in dicts


# ====================================================================
# 13. Combination limit exceeded
# ====================================================================
def test_combination_limit_exceeded():
    """Too many filter combos → empty list, no truncation."""
    dicts, warnings = _build_filter_dicts(
        RetrievalFilters(
            years=[2014, 2018, 2022],
            team_ids=["t1", "t2", "t3", "t4"],
        ),
        max_combinations=5,
    )
    assert dicts == []  # not truncated — aborted


def test_combination_limit_exceeded_error_code():
    """Gateway returns VALIDATION_ERROR, does not call D."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured),
        query_with_rerank_fn=_fake_rerank(),
        max_filter_combinations=3,
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(
                    years=[2014, 2018, 2022],
                    team_ids=["t1", "t2", "t3"],
                )
            )
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert result.error is not None
    assert result.error.code == "VALIDATION_ERROR"
    assert result.error.component == "retrieval"
    assert result.error.retryable is False
    assert len(captured) == 0  # D was never called


def test_combination_limit_exceeded_no_d_call():
    """When combos exceed limit, no D function is ever invoked."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured),
        query_with_rerank_fn=_fake_rerank(),
        max_filter_combinations=2,
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(
                    years=[2018, 2022],
                    stages=["final", "semi_final"],
                )
            )
        )

    result = _run(_test())
    assert result.status == RAGStatus.error
    assert len(captured) == 0


def test_combination_limit_exceeded_applied_filters_preserved():
    """applied_filters must match request even on error."""
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(),
        query_with_rerank_fn=_fake_rerank(),
        max_filter_combinations=2,
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(
                    years=[2014, 2018, 2022],
                    stages=["final"],
                    team_ids=["team_ARG"],
                )
            )
        )

    result = _run(_test())
    assert result.applied_filters.years == [2014, 2018, 2022]
    assert result.applied_filters.stages == ["final"]
    assert result.applied_filters.team_ids == ["team_ARG"]


# ====================================================================
# 14. result_types post-filter
# ====================================================================
def test_result_types_post_filter():
    """Only items with matching result_type survive."""
    _m = _required_meta
    raw = [
        _fake_d_item("c1", metadata={**_m, "result_type": "penalties"}),
        _fake_d_item("c2", metadata={**_m, "result_type": "regulation"}),
    ]
    kept, dropped = _post_filter_raw(
        raw, RetrievalFilters(result_types=["penalties"])
    )
    assert len(kept) == 1
    assert kept[0]["id"] == "c1"
    assert dropped == 1


# ====================================================================
# 15. match_ids post-filter
# ====================================================================
def test_match_ids_post_filter():
    _m = _required_meta
    raw = [
        _fake_d_item("c1", metadata={**_m, "match_id": "M-1"}),
        _fake_d_item("c2", metadata={**_m, "match_id": "M-2"}),
    ]
    kept, dropped = _post_filter_raw(
        raw, RetrievalFilters(match_ids=["M-1"])
    )
    assert len(kept) == 1
    assert kept[0]["id"] == "c1"
    assert dropped == 1


# ====================================================================
# 16. Hard-filter candidates removed
# ====================================================================
def test_hard_filter_candidates_removed():
    """Items not matching filter are excluded from final result."""
    _m = _required_meta
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[
                _fake_d_item("c1", metadata={**_m, "match_id": "M-1", "result_type": "regulation"}),
                _fake_d_item("c2", metadata={**_m, "match_id": "M-2", "result_type": "penalties"}),
            ],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(match_ids=["M-1"])
            )
        )

    result = _run(_test())
    assert len(result.items) == 1
    assert result.items[0].chunk_id == "c1"


# ====================================================================
# 17. Chunk deduplication
# ====================================================================
def test_chunk_deduplication():
    """Two filter combos returning the same chunk_id → only one kept."""
    captured: list[dict] = []
    item = _fake_d_item("dup-1")
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[item, item.copy()],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(years=[2018, 2022])
            )
        )

    result = _run(_test())
    # 2 filter combos × 1 item each = both return same chunk_id → deduped to 1
    assert len(result.items) == 1
    assert result.items[0].chunk_id == "dup-1"


# ====================================================================
# 18. Distance sorting
# ====================================================================
def test_distance_sorting():
    """Items sorted by distance ascending."""
    e1 = EvidenceItem(
        chunk_id="c1", document_id="d", source_id="s",
        document_name="T", text="...", data_version="v1",
        vector_distance=0.5,
    )
    e2 = EvidenceItem(
        chunk_id="c2", document_id="d", source_id="s",
        document_name="T", text="...", data_version="v1",
        vector_distance=0.1,
    )
    sorted_items = _sort_items([e1, e2], rerank_applied=False)
    assert sorted_items[0].chunk_id == "c2"  # closer distance first


# ====================================================================
# 19. Rerank score sorting
# ====================================================================
def test_rerank_score_sorting():
    """When reranker applied, sort by rerank_score descending."""
    e1 = EvidenceItem(
        chunk_id="c1", document_id="d", source_id="s",
        document_name="T", text="...", data_version="v1",
        rerank_score=0.3, vector_distance=0.5,
    )
    e2 = EvidenceItem(
        chunk_id="c2", document_id="d", source_id="s",
        document_name="T", text="...", data_version="v1",
        rerank_score=0.9, vector_distance=0.8,
    )
    sorted_items = _sort_items([e1, e2], rerank_applied=True)
    assert sorted_items[0].chunk_id == "c2"  # higher rerank_score first


# ====================================================================
# 20. retrieval_rank assigned
# ====================================================================
def test_retrieval_rank_assigned():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[_fake_d_item("c1", distance=0.1), _fake_d_item("c2", distance=0.5)],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.items[0].retrieval_rank == 1
    assert result.items[1].retrieval_rank == 2


# ====================================================================
# 21. rerank_rank assigned
# ====================================================================
def test_rerank_rank_without_reranker_is_none():
    """When reranker not applied, rerank_rank is None."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[_fake_d_item("c1")],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.items[0].rerank_rank is None


def test_rerank_rank_with_reranker_is_set():
    """When reranker applied, rerank_rank is assigned."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(),
        query_with_rerank_fn=_fake_rerank(
            captured=captured,
            items=[
                _fake_d_item("c1", rerank_score=0.9),
                _fake_d_item("c2", rerank_score=0.5),
            ],
        ),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                options=RAGOptions(
                    use_query_rewrite=True,
                    use_reranker=True,
                    retrieval_top_k=10,
                    rerank_top_n=5,
                )
            )
        )

    result = _run(_test())
    assert result.items[0].rerank_rank == 1
    assert result.items[1].rerank_rank == 2


# ====================================================================
# 22. Missing required metadata — candidate dropped
# ====================================================================
def test_missing_required_metadata_dropped():
    """Item without source_id → not mapped to EvidenceItem."""
    raw = _fake_d_item("bad", metadata={
        "document_id": "d1",
        "document_name": "Test Doc",
        "data_version": "v1",
        # source_id intentionally omitted
    })
    ev, missing = _map_to_evidence(raw)
    assert ev is None
    assert "source_id" in missing


# ====================================================================
# 23. trace_id passthrough
# ====================================================================
def test_trace_id_passthrough():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item()]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request(trace_id="my-unique-trace"))

    result = _run(_test())
    assert result.trace_id == "my-unique-trace"


# ====================================================================
# 24. contract_version passthrough
# ====================================================================
def test_contract_version_passthrough():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item()]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.contract_version == RAG_CONTRACT_VERSION


# ====================================================================
# 25. applied_filters preserved
# ====================================================================
def test_applied_filters_preserved():
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item()]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(
                    years=[2022],
                    stages=["final"],
                    team_ids=["team_ARG"],
                )
            )
        )

    result = _run(_test())
    assert result.applied_filters.years == [2022]
    assert result.applied_filters.stages == ["final"]
    assert result.applied_filters.team_ids == ["team_ARG"]


# ====================================================================
# 26. Reranker requested but not executed → degraded
# ====================================================================
def test_reranker_requested_but_not_executed_degraded():
    """use_reranker=true but D returns no rerank_score → degraded."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(),
        query_with_rerank_fn=_fake_rerank(
            captured=captured,
            items=[_fake_d_item("c1", rerank_score=None)],  # no rerank score
        ),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                options=RAGOptions(
                    use_query_rewrite=True,
                    use_reranker=True,
                )
            )
        )

    result = _run(_test())
    assert result.rerank_applied is False
    assert result.status == RAGStatus.degraded


# ====================================================================
# 27. rewrite=false + reranker=true → safe degrade
# ====================================================================
def test_rewrite_false_reranker_true_safe_degrade():
    """D cannot do reranker without rewrite → degrade to query_top_k."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item("c1")]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                options=RAGOptions(
                    use_query_rewrite=False,
                    use_reranker=True,
                )
            )
        )

    result = _run(_test())
    # Should have called query_top_k, not query_with_rerank
    assert len(captured) == 1
    assert captured[0].get("use_query_rewrite") is False
    assert result.rerank_applied is False
    codes = {w.code for w in result.warnings}
    assert "RERANKER_UNAVAILABLE" in codes
    assert result.status == RAGStatus.degraded


# ====================================================================
# 28. No fabricated source_id
# ====================================================================
def test_no_fabricated_source_id():
    """source_id comes from metadata, never invented."""
    raw = _fake_d_item(
        "c1",
        metadata={
            "source_id": "src-real-42",
            "document_id": "doc-1",
            "document_name": "Real Doc",
            "data_version": "v1",
        },
    )
    ev, missing = _map_to_evidence(raw)
    assert ev is not None
    assert ev.source_id == "src-real-42"
    assert missing == []


# ====================================================================
# 29. Error message does not leak absolute paths
# ====================================================================
def test_error_message_no_absolute_path():
    """ErrorItem.message must not contain absolute paths."""
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(should_raise=OSError("C:\\data\\chroma\\broken")),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(_make_request())

    result = _run(_test())
    assert result.error is not None
    msg = result.error.message
    assert "C:\\" not in msg
    assert "D:\\" not in msg
    assert "/home/" not in msg
    assert "chroma" not in msg.lower()


# ====================================================================
# 30. Final items not exceed rerank_top_n
# ====================================================================
def test_final_items_not_exceed_rerank_top_n():
    """len(result.items) <= rerank_top_n."""
    many = [_fake_d_item(f"c{i}", distance=0.1 * i) for i in range(20)]
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=many),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                options=RAGOptions(retrieval_top_k=20, rerank_top_n=5)
            )
        )

    result = _run(_test())
    assert len(result.items) <= 5


# ====================================================================
# 31. No results with all filters
# ====================================================================
def test_no_filter_returns_none():
    """Empty RetrievalFilters → [None] (no Chroma where filter)."""
    dicts, _ = _build_filter_dicts(RetrievalFilters())
    assert dicts == [None]


# ====================================================================
# 32. Query rewrite enabled sets degraded
# ====================================================================
def test_query_rewrite_enabled_sets_degraded():
    """When use_query_rewrite=true, D can't confirm → status=degraded."""
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(captured=captured, items=[_fake_d_item()]),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                options=RAGOptions(use_query_rewrite=True, use_reranker=False)
            )
        )

    result = _run(_test())
    assert result.rewrite_applied is False
    assert result.status == RAGStatus.degraded
    codes = {w.code for w in result.warnings}
    assert "QUERY_REWRITE_UNAVAILABLE" in codes


# ====================================================================
# 33. Source URL alias mapping
# ====================================================================
def test_source_metadata_alias_mapping():
    """url field aliased to source_url."""
    raw = _fake_d_item(metadata={
        "source_id": "s1", "document_id": "d1", "document_name": "T",
        "data_version": "v1", "url": "https://example.com/report.pdf",
    })
    ev, missing = _map_to_evidence(raw)
    assert ev is not None
    assert ev.source_url == "https://example.com/report.pdf"


# ====================================================================
# 34. source_page alias mapping
# ====================================================================
def test_source_page_alias_mapping():
    """page field aliased to source_page."""
    raw = _fake_d_item(metadata={
        "source_id": "s1", "document_id": "d1", "document_name": "T",
        "data_version": "v1", "page": 42,
    })
    ev, missing = _map_to_evidence(raw)
    assert ev is not None
    assert ev.source_page == 42


# ====================================================================
# 35. _deduplicate_by_chunk_id keeps best
# ====================================================================
def test_deduplicate_keeps_best_rerank():
    e1 = EvidenceItem(chunk_id="dup", document_id="d", source_id="s",
                      document_name="T", text="...", data_version="v1",
                      rerank_score=0.9, vector_distance=0.5)
    e2 = EvidenceItem(chunk_id="dup", document_id="d", source_id="s",
                      document_name="T", text="...", data_version="v1",
                      rerank_score=0.3, vector_distance=0.1)
    result = _deduplicate_by_chunk_id([e1, e2])
    assert len(result) == 1
    assert result[0].rerank_score == 0.9  # best rerank kept


# ====================================================================
# 36. Post-filter degraded status (match_ids)
# ====================================================================
def test_match_ids_post_filter_sets_degraded():
    """When match_ids are used, status must be degraded."""
    _m = _required_meta
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[_fake_d_item("c1", metadata={**_m, "match_id": "M-1"})],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(match_ids=["M-1"])
            )
        )

    result = _run(_test())
    assert result.status == RAGStatus.degraded
    codes = {w.code for w in result.warnings}
    assert "RETRIEVAL_DEGRADED" in codes
    assert len(result.items) == 1
    assert result.items[0].match_id == "M-1"


# ====================================================================
# 37. Post-filter degraded status (result_types)
# ====================================================================
def test_result_types_post_filter_sets_degraded():
    """When result_types are used, status must be degraded."""
    _m = _required_meta
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[_fake_d_item("c1", metadata={**_m, "result_type": "penalties"})],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(result_types=["penalties"])
            )
        )

    result = _run(_test())
    assert result.status == RAGStatus.degraded
    codes = {w.code for w in result.warnings}
    assert "RETRIEVAL_DEGRADED" in codes
    assert len(result.items) == 1


# ====================================================================
# 38. Post-filter excludes non-matching items
# ====================================================================
def test_post_filter_non_matching_items_excluded():
    """Items not matching result_types/match_ids must not appear."""
    _m = _required_meta
    captured: list[dict] = []
    gw = ChromaRetrievalGateway(
        query_top_k_fn=_fake_top_k(
            captured=captured,
            items=[
                _fake_d_item("c1", metadata={**_m, "match_id": "M-1", "result_type": "regulation"}),
                _fake_d_item("c2", metadata={**_m, "match_id": "M-2", "result_type": "penalties"}),
            ],
        ),
        query_with_rerank_fn=_fake_rerank(),
    )

    async def _test():
        return await gw.retrieve(
            _make_request(
                filters=RetrievalFilters(
                    match_ids=["M-1"],
                    result_types=["regulation"],
                )
            )
        )

    result = _run(_test())
    assert len(result.items) == 1
    assert result.items[0].chunk_id == "c1"
    assert result.items[0].match_id == "M-1"
