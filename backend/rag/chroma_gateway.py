"""ChromaRetrievalGateway — adapts D's sync Chroma functions to the async
RetrievalGateway protocol (rag-v1.1-draft).

This module does NOT load Chroma, BGE, or Reranker at import time.
D functions are imported lazily on first ``retrieve()`` call.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    EvidenceItem,
    RAGOptions,
    RAGStatus,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTiming,
    WarningItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_COLLECTION_FACTS: str = "world_cup_match_facts"
_MAX_FILTER_COMBINATIONS: int = 8

# Required metadata keys for a valid EvidenceItem.  If any of these is
# missing the candidate is dropped with a structured warning.
_REQUIRED_METADATA: tuple[str, ...] = (
    "source_id",
    "document_id",
    "document_name",
    "data_version",
)

# Aliases the adapter accepts when looking for metadata values — avoids
# guessing field names scattered across the codebase.
_SOURCE_ID_KEYS: tuple[str, ...] = ("source_id", "source", "source_ids")
_DOCUMENT_ID_KEYS: tuple[str, ...] = ("document_id", "document_name")
_DOCUMENT_NAME_KEYS: tuple[str, ...] = ("document_name", "title")
_SOURCE_URL_KEYS: tuple[str, ...] = ("source_url", "url")
_SOURCE_PAGE_KEYS: tuple[str, ...] = ("source_page", "page")


# ===================================================================
# Gateway
# ===================================================================
class ChromaRetrievalGateway:
    """Adapt D's synchronous Chroma retrieval to the async protocol.

    Constructor accepts injectable callables for testing.  When they
    are ``None`` (production), the real D functions are lazy-imported
    from ``backend.services.chroma_service`` on the first call.
    """

    def __init__(
        self,
        *,
        query_top_k_fn: Callable[..., list[dict]] | None = None,
        query_with_rerank_fn: Callable[..., list[dict]] | None = None,
        collection: str = _COLLECTION_FACTS,
        max_filter_combinations: int = _MAX_FILTER_COMBINATIONS,
    ) -> None:
        self._top_k = query_top_k_fn
        self._rerank = query_with_rerank_fn
        self._collection = collection
        self._max_combos = max_filter_combinations
        self._resolved = query_top_k_fn is not None and query_with_rerank_fn is not None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Run Chroma retrieval and return a typed ``RetrievalResult``."""
        t0 = time.monotonic()
        self._resolve_functions()

        opts: RAGOptions = request.options
        warnings: list[WarningItem] = []

        # --- 1. Build D-compatible filter dicts --------------------------
        filter_dicts, filter_warnings = _build_filter_dicts(
            request.filters, max_combinations=self._max_combos
        )
        warnings.extend(filter_warnings)

        # Empty list (not [None]) signals combination limit exceeded →
        # abort with VALIDATION_ERROR before any D call.
        if not filter_dicts:
            return _error_result(
                request,
                ErrorItem(
                    code="VALIDATION_ERROR",
                    message="过滤条件组合数超过安全上限，无法执行检索。",
                    component="retrieval",
                    retryable=False,
                ),
                timing=RetrievalTiming(total_ms=_elapsed_ms(t0)),
            )

        # --- 2. Determine retrieval strategy -----------------------------
        use_reranker = opts.use_reranker
        use_rewrite = opts.use_query_rewrite
        reranker_requested = use_reranker  # track original intent

        if use_reranker and not use_rewrite:
            # D's query_with_rerank hardcodes use_query_rewrite=True.
            # We cannot satisfy reranker-without-rewrite — degrade.
            use_reranker = False
            warnings.append(
                WarningItem(
                    code="RERANKER_UNAVAILABLE",
                    message=(
                        "当前检索接口不支持独立启用 Reranker"
                        "（需同时启用 Query Rewrite），已降级为纯向量检索。"
                    ),
                    component="retrieval",
                    retryable=False,
                )
            )

        # --- 3. Execute retrieval (fan-out over filter combinations) -----
        retrieval_ms = 0
        rerank_ms = 0
        rerank_applied = False
        all_raw: list[dict] = []

        try:
            coro = self._fan_out_retrieval(
                query=request.query,
                opts=opts,
                filter_dicts=filter_dicts,
                use_reranker=use_reranker,
                use_rewrite=use_rewrite,
            )
            all_raw, retrieval_ms = await asyncio.wait_for(
                coro, timeout=opts.timeout_ms / 1000.0
            )
        except TimeoutError:
            return _error_result(
                request,
                ErrorItem(
                    code="TIMEOUT",
                    message="知识库检索超时，请稍后重试。",
                    component="retrieval",
                    retryable=True,
                ),
                timing=RetrievalTiming(total_ms=_elapsed_ms(t0)),
            )
        except Exception:
            logger.exception("Chroma retrieval failed")
            return _error_result(
                request,
                ErrorItem(
                    code="RETRIEVAL_ERROR",
                    message="知识库检索暂时不可用。",
                    component="retrieval",
                    retryable=True,
                ),
                timing=RetrievalTiming(total_ms=_elapsed_ms(t0)),
            )

        # --- 4. Post-filter raw items (result_types, match_ids) ---------
        # D does not natively support result_types / match_ids in its
        # Chroma where filter.  Post-filtering is applied here but MUST
        # be flagged as degraded — never claim native filtering.
        _has_post_filter = bool(
            request.filters.result_types or request.filters.match_ids
        )
        post_filter_degraded = False
        all_raw, pf_dropped = _post_filter_raw(all_raw, request.filters)
        if _has_post_filter:
            post_filter_degraded = True
            warnings.append(
                WarningItem(
                    code="RETRIEVAL_DEGRADED",
                    message=(
                        "result_types / match_ids 当前仅支持后置过滤，"
                        "非 Chroma 原生能力，检索可能不完整。"
                    ),
                    component="retrieval",
                    retryable=False,
                )
            )
        if pf_dropped > 0:
            logger.info("Post-filter dropped %d raw candidates", pf_dropped)

        # --- 5. Map raw items → EvidenceItem -----------------------------
        evidence_items: list[EvidenceItem] = []
        dropped = 0
        for raw in all_raw:
            ev, missing = _map_to_evidence(raw)
            if ev is not None:
                evidence_items.append(ev)
            else:
                dropped += 1
                logger.warning(
                    "Dropped candidate %s — missing required fields: %s",
                    raw.get("id", "?"),
                    missing,
                )

        if dropped > 0:
            warnings.append(
                WarningItem(
                    code="RETRIEVAL_DEGRADED",
                    message=f"检索结果中 {dropped} 条候选因缺少必要元数据被丢弃。",
                    component="retrieval",
                    retryable=False,
                )
            )

        # --- 7. Deduplicate, sort, rank, truncate ------------------------
        evidence_items = _deduplicate_by_chunk_id(evidence_items)
        rerank_applied = use_reranker and any(
            e.rerank_score is not None for e in evidence_items
        )
        evidence_items = _sort_items(evidence_items, rerank_applied=rerank_applied)
        _assign_ranks(evidence_items, rerank_applied=rerank_applied)
        evidence_items = evidence_items[: opts.rerank_top_n]

        # --- 8. Rewrite status -------------------------------------------
        rewrite_applied = False
        rewritten_queries: list[str] = []
        rewrite_degraded = False
        if use_rewrite:
            # D's query_top_k does not expose rewritten_queries metadata.
            # We honestly report that we cannot confirm rewrite execution.
            warnings.append(
                WarningItem(
                    code="QUERY_REWRITE_UNAVAILABLE",
                    message="当前检索接口未暴露 Query Rewrite 执行元数据，无法确认改写状态。",
                    component="retrieval",
                    retryable=False,
                )
            )
            rewrite_degraded = True

        # --- 9. Determine final status -----------------------------------
        status = _determine_status(
            evidence_items,
            use_reranker=reranker_requested,
            rerank_applied=rerank_applied,
            had_dropped_candidates=(dropped > 0),
            rewrite_degraded=rewrite_degraded,
            post_filter_degraded=post_filter_degraded,
        )

        if status == RAGStatus.empty:
            warnings.append(
                WarningItem(
                    code="NO_RESULT",
                    message="没有找到可靠的事实或证据。",
                    component="retrieval",
                    retryable=False,
                )
            )

        # --- 10. Assemble result -------------------------------------------
        return RetrievalResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            status=status,
            original_query=request.query,
            rewritten_queries=rewritten_queries,
            items=evidence_items,
            applied_filters=request.filters,
            rewrite_applied=rewrite_applied,
            rerank_applied=rerank_applied,
            warnings=warnings,
            timing=RetrievalTiming(
                retrieval_ms=retrieval_ms,
                rerank_ms=rerank_ms,
                total_ms=_elapsed_ms(t0),
            ),
            error=None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_functions(self) -> None:
        """Lazy-import D functions on first call (never at import time)."""
        if self._resolved:
            return
        from backend.services.chroma_service import (  # noqa: E402
            query_top_k,
            query_with_rerank,
        )

        if self._top_k is None:
            self._top_k = query_top_k
        if self._rerank is None:
            self._rerank = query_with_rerank
        self._resolved = True

    async def _fan_out_retrieval(
        self,
        query: str,
        opts: RAGOptions,
        filter_dicts: list[dict | None],
        use_reranker: bool,
        use_rewrite: bool,
    ) -> tuple[list[dict], int]:
        """Call D across filter combinations, merge & deduplicate."""
        t_retrieval = time.monotonic()

        if use_reranker:
            k = opts.rerank_top_n
            d_fn = self._rerank
        else:
            k = opts.retrieval_top_k
            d_fn = self._top_k

        all_raw: list[dict] = []
        for fd in filter_dicts:
            batch = await asyncio.to_thread(
                _call_d_function,
                d_fn=d_fn,
                query_text=query,
                k=k,
                collection=self._collection,
                filter_dict=fd,
                use_reranker=use_reranker,
                use_rewrite=use_rewrite,
                recall_k=opts.retrieval_top_k,
            )
            all_raw.extend(batch)

        retrieval_ms = _elapsed_ms(t_retrieval)
        return all_raw, retrieval_ms


# ===================================================================
# Module-level helpers (not methods — pure functions for testability)
# ===================================================================


def _call_d_function(
    d_fn: Callable[..., list[dict]],
    query_text: str,
    k: int,
    collection: str,
    filter_dict: dict | None,
    use_reranker: bool,
    use_rewrite: bool,
    recall_k: int,
) -> list[dict]:
    """Call the appropriate D function with the right signature.

    Extracted as a module-level function so tests can verify the call
    parameters without mocking asyncio.
    """
    if use_reranker:
        return d_fn(
            query_text=query_text,
            k=k,
            collection=collection,
            filters=filter_dict,
            recall_k=recall_k,
        )
    else:
        return d_fn(
            query_text=query_text,
            k=k,
            collection=collection,
            filters=filter_dict,
            use_query_rewrite=use_rewrite,
        )


def _build_filter_dicts(
    filters: RetrievalFilters,
    max_combinations: int = _MAX_FILTER_COMBINATIONS,
) -> tuple[list[dict | None], list[WarningItem]]:
    """Convert shared RetrievalFilters → list of D-compatible dicts.

    Returns ([filter_dict, ...], [warnings]).
    An empty list means "no valid combination could be produced".
    ``None`` entries mean "query without Chroma where filter".
    """
    warnings: list[WarningItem] = []

    # Gather non-empty value lists
    year_vals = [y for y in filters.years]
    team_vals = [t for t in filters.team_ids]
    stage_vals = [s.value if hasattr(s, "value") else s for s in filters.stages]

    if not year_vals and not team_vals and not stage_vals:
        return [None], warnings

    # Build single-value combinations
    combos: list[dict] = []
    if year_vals:
        for y in year_vals:
            combos.append({"tournament_year": y})
    if team_vals:
        new_combos: list[dict] = []
        for c in combos or [{}]:
            for t in team_vals:
                new_combos.append({**c, "team_id": t})
        combos = new_combos
    if stage_vals:
        new_combos = []
        for c in combos or [{}]:
            for s in stage_vals:
                new_combos.append({**c, "stage_enum": s})
        combos = new_combos

    if not combos:
        combos = [{}]

    # Reject when combinations exceed safety limit — never truncate silently.
    # Returning an empty list signals to the caller that retrieval must abort.
    if len(combos) > max_combinations:
        return [], warnings

    return combos, warnings


def _normalize_source_id(metadata: dict) -> str | None:
    """Normalize a source identifier from Chroma metadata into a scalar string.

    Priority (deterministic, no sorting, no JSON encoding):
    1. ``metadata["source_id"]`` — non-empty string
    2. ``metadata["source"]``  — non-empty string
    3. ``metadata["source_ids"]`` — if string, use verbatim;
       if list/tuple, pick the **first** non-empty string element.

    Returns ``None`` when no valid source can be resolved.  The original
    *metadata* dict is never mutated.
    """
    # 1. source_id (scalar string)
    v = metadata.get("source_id")
    if isinstance(v, str) and v:
        return v

    # 2. source (scalar string)
    v = metadata.get("source")
    if isinstance(v, str) and v:
        return v

    # 3. source_ids (string, or list/tuple → first non-empty string)
    v = metadata.get("source_ids")
    if isinstance(v, str) and v:
        return v
    if isinstance(v, (list, tuple)):
        for item in v:
            if isinstance(item, str) and item:
                return item

    return None


def _map_to_evidence(raw: dict) -> tuple[EvidenceItem | None, list[str]]:
    """Map a raw D item dict → EvidenceItem.  Returns (None, [missing]) on failure."""
    metadata: dict = raw.get("metadata", {}) or {}
    missing: list[str] = []

    def _get(keys: tuple[str, ...]) -> str | None:
        for k in keys:
            v = metadata.get(k)
            if v is not None and v != "":
                return v
        return raw.get(keys[0]) if isinstance(raw.get(keys[0]), str) else None

    source_id = _normalize_source_id(metadata)
    if not source_id:
        # Legacy fallback: try raw top-level keys (backward compat)
        for k in _SOURCE_ID_KEYS:
            raw_val = raw.get(k)
            if isinstance(raw_val, str) and raw_val:
                source_id = raw_val
                break
    document_id = _get(_DOCUMENT_ID_KEYS)
    document_name = _get(_DOCUMENT_NAME_KEYS)
    data_version = metadata.get("data_version") or raw.get("data_version")

    for field_name, value in [
        ("source_id", source_id),
        ("document_id", document_id),
        ("document_name", document_name),
        ("data_version", data_version),
    ]:
        if not value:
            missing.append(field_name)

    if missing:
        return None, missing

    return (
        EvidenceItem(
            chunk_id=raw.get("id", ""),
            document_id=document_id,  # type: ignore[arg-type]
            collection=raw.get("collection"),
            match_id=metadata.get("match_id"),
            source_id=source_id,  # type: ignore[arg-type]
            document_name=document_name,  # type: ignore[arg-type]
            source_url=_get(_SOURCE_URL_KEYS),
            source_page=_safe_int(metadata, _SOURCE_PAGE_KEYS),
            text=raw.get("document", ""),
            language=metadata.get("language"),
            data_version=data_version,  # type: ignore[arg-type]
            chunk_index=_safe_int(metadata, ("chunk_index",)),
            vector_distance=raw.get("distance"),
            rerank_score=raw.get("rerank_score"),
        ),
        [],
    )


def _safe_int(metadata: dict, keys: tuple[str, ...]) -> int | None:
    for k in keys:
        v = metadata.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
    return None


def _post_filter(
    items: list[EvidenceItem], filters: RetrievalFilters
) -> tuple[list[EvidenceItem], int]:
    """Remove items not matching result_types or match_ids hard constraints."""
    rt_filter = set(
        rt.value if hasattr(rt, "value") else rt for rt in filters.result_types
    )
    mid_filter = set(filters.match_ids)

    if not rt_filter and not mid_filter:
        return items, 0

    kept: list[EvidenceItem] = []
    dropped = 0
    for item in items:
        # match_id check
        if mid_filter and item.match_id not in mid_filter:
            dropped += 1
            continue
        # result_type check — we don't have result_type on EvidenceItem,
        # so this must come from metadata.  Since EvidenceItem doesn't
        # carry raw metadata, we skip this here; post-filtering for
        # result_types is done on the raw items before mapping.
        kept.append(item)

    return kept, dropped


def _post_filter_raw(
    raw_items: list[dict], filters: RetrievalFilters
) -> tuple[list[dict], int]:
    """Post-filter raw D items before EvidenceItem mapping."""
    rt_filter = set(
        rt.value if hasattr(rt, "value") else rt for rt in filters.result_types
    )
    mid_filter = set(filters.match_ids)

    if not rt_filter and not mid_filter:
        return raw_items, 0

    kept: list[dict] = []
    dropped = 0
    for item in raw_items:
        metadata: dict = item.get("metadata", {}) or {}
        if mid_filter and metadata.get("match_id") not in mid_filter:
            dropped += 1
            continue
        if rt_filter and metadata.get("result_type") not in rt_filter:
            dropped += 1
            continue
        kept.append(item)

    return kept, dropped


def _deduplicate_by_chunk_id(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Keep the best entry per chunk_id.

    Precedence: (1) both have rerank → higher rerank_score wins;
    (2) one has rerank → that one wins;
    (3) neither has rerank → lower vector_distance wins.
    """
    seen: dict[str, EvidenceItem] = {}
    for item in items:
        cid = item.chunk_id
        if cid not in seen:
            seen[cid] = item
            continue
        existing = seen[cid]

        item_has_rerank = item.rerank_score is not None
        exist_has_rerank = existing.rerank_score is not None

        if item_has_rerank and exist_has_rerank:
            if item.rerank_score > existing.rerank_score:
                seen[cid] = item
        elif item_has_rerank and not exist_has_rerank:
            seen[cid] = item
        elif not item_has_rerank and not exist_has_rerank:
            if (
                item.vector_distance is not None
                and existing.vector_distance is not None
                and item.vector_distance < existing.vector_distance
            ):
                seen[cid] = item
        # else: existing has rerank and item doesn't → keep existing
    return list(seen.values())


def _sort_items(
    items: list[EvidenceItem], *, rerank_applied: bool
) -> list[EvidenceItem]:
    """Stable sort: rerank_score desc (if applied), else distance asc."""
    if rerank_applied:

        def _key(e: EvidenceItem) -> tuple[int, float]:
            score = e.rerank_score if e.rerank_score is not None else -999.0
            return (0, -score)  # negate for descending

    else:

        def _key(e: EvidenceItem) -> tuple[int, float]:
            dist = e.vector_distance if e.vector_distance is not None else 999.0
            return (1, dist)  # ascending

    return sorted(items, key=_key)


def _assign_ranks(items: list[EvidenceItem], *, rerank_applied: bool) -> None:
    """Mutate items in-place, assigning retrieval_rank and rerank_rank."""
    for i, item in enumerate(items, start=1):
        item.retrieval_rank = i
        if rerank_applied and item.rerank_score is not None:
            item.rerank_rank = i
        # else: rerank_rank stays None


def _determine_status(
    items: list[EvidenceItem],
    *,
    use_reranker: bool,
    rerank_applied: bool,
    had_dropped_candidates: bool,
    rewrite_degraded: bool = False,
    post_filter_degraded: bool = False,
) -> RAGStatus:
    if not items:
        return RAGStatus.empty
    if rewrite_degraded:
        return RAGStatus.degraded
    if use_reranker and not rerank_applied:
        return RAGStatus.degraded
    if had_dropped_candidates:
        return RAGStatus.degraded
    if post_filter_degraded:
        return RAGStatus.degraded
    return RAGStatus.ok


def _error_result(
    request: RetrievalRequest,
    error: ErrorItem,
    timing: RetrievalTiming | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id=request.trace_id,
        status=RAGStatus.error,
        original_query=request.query,
        rewritten_queries=[],
        items=[],
        applied_filters=request.filters,
        rewrite_applied=False,
        rerank_applied=False,
        warnings=[],
        timing=timing or RetrievalTiming(),
        error=error,
    )


def _elapsed_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)
