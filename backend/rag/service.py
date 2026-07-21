"""RagService — in-process async entry point for B→E generation.

B calls ``RagService.generate(request: RAGRequest) -> RAGResult`` via
async Python (no internal HTTP).  The service orchestrates:

1. Retrieval via ``RetrievalGateway`` (D)
2. Generation via ``GenerationClient`` (LLM)
3. Status, warning, timing, and error assembly

This module never loads models, reads SQLite, initialises Chroma, or
reads API keys.  When dependencies are not configured it returns a
safe ``status=error`` result — never a fabricated success.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from backend.schemas.rag_contract import (
    RAG_CONTRACT_VERSION,
    ErrorItem,
    GenerationMeta,
    RAGRequest,
    RAGResult,
    RAGStatus,
    RAGTiming,
    RetrievalRequest,
    RetrievalTiming,
    WarningItem,
)

if TYPE_CHECKING:
    from backend.rag.protocols import GenerationClient, RetrievalGateway


class RagService:
    """RAG generation orchestrator.

    Constructor receives protocol implementations via dependency
    injection.  When either gateway is ``None`` the service returns a
    safe error — it never silently degrades to fabricated answers.
    """

    def __init__(
        self,
        retrieval: RetrievalGateway | None = None,
        generation: GenerationClient | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._generation = generation

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def generate(self, request: RAGRequest) -> RAGResult:
        """Run the full retrieval → generation pipeline.

        Returns a ``RAGResult`` whose ``trace_id`` matches the request.
        """
        t0 = time.monotonic()

        # -- 0. Dependency check ---------------------------------------
        if self._retrieval is None or self._generation is None:
            return _error_result(
                request,
                ErrorItem(
                    code="INTERNAL_ERROR",
                    message="RAG 服务未配置，无法处理请求。",
                    component="rag_service",
                    retryable=False,
                ),
                retrieval_timing=None,
                t0=t0,
            )

        # -- 1. Retrieval ----------------------------------------------
        retrieval_req = RetrievalRequest(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            query=request.question,
            original_question=request.original_question,
            filters=request.filters,
            options=request.options,
        )

        try:
            retrieval_result = await self._retrieval.retrieve(retrieval_req)
        except Exception:
            return _error_result(
                request,
                ErrorItem(
                    code="RETRIEVAL_ERROR",
                    message="知识库检索暂时不可用。",
                    component="retrieval",
                    retryable=True,
                ),
                retrieval_timing=None,
                t0=t0,
            )

        warnings: list[WarningItem] = list(retrieval_result.warnings)
        retrieval_timing = retrieval_result.timing

        # -- 1a. Retrieval returned error status -----------------------
        if retrieval_result.status == RAGStatus.error:
            return _error_result(
                request,
                retrieval_result.error
                or ErrorItem(
                    code="RETRIEVAL_ERROR",
                    message="检索失败，无法继续处理。",
                    component="retrieval",
                    retryable=True,
                ),
                retrieval_timing=retrieval_timing,
                t0=t0,
            )

        # -- 1b. Empty result ------------------------------------------
        if not retrieval_result.items and retrieval_result.status != RAGStatus.degraded:
            return RAGResult(
                contract_version=RAG_CONTRACT_VERSION,
                trace_id=request.trace_id,
                status=RAGStatus.empty,
                answer="未找到与您的问题相关的可靠信息。",
                facts=[],
                sources=[],
                evidence=[],
                applied_filters=retrieval_result.applied_filters,
                confidence=None,
                rewrite_applied=retrieval_result.rewrite_applied,
                rerank_applied=retrieval_result.rerank_applied,
                warnings=[
                    WarningItem(
                        code="NO_RESULT",
                        message="没有找到可靠的事实或证据。",
                        component="retrieval",
                        retryable=False,
                    ),
                    *warnings,
                ],
                timing=RAGTiming(
                    rewrite_ms=retrieval_timing.rewrite_ms,
                    retrieval_ms=retrieval_timing.retrieval_ms,
                    rerank_ms=retrieval_timing.rerank_ms,
                    total_ms=_elapsed_ms(t0),
                ),
                generation_meta=GenerationMeta(),
                error=None,
            )

        # -- 2. Generation ---------------------------------------------
        gen_t0 = time.monotonic()
        try:
            gen_result = await self._generation.generate(request, retrieval_result)
        except Exception:
            return _error_result(
                request,
                ErrorItem(
                    code="GENERATION_ERROR",
                    message="答案生成暂时不可用。",
                    component="generation",
                    retryable=True,
                ),
                retrieval_timing=retrieval_timing,
                t0=t0,
            )

        generation_ms = _elapsed_ms(gen_t0)

        # -- 3. Merge warnings and determine final status ---------------
        warnings.extend(gen_result.warnings)

        if retrieval_result.status == RAGStatus.degraded:
            final_status = RAGStatus.degraded
        elif gen_result.status == RAGStatus.degraded:
            final_status = RAGStatus.degraded
        else:
            final_status = RAGStatus.ok

        # -- 4. Assemble result ----------------------------------------
        return RAGResult(
            contract_version=RAG_CONTRACT_VERSION,
            trace_id=request.trace_id,
            status=final_status,
            answer=gen_result.answer,
            facts=gen_result.facts,
            sources=gen_result.sources,
            evidence=retrieval_result.items,
            applied_filters=retrieval_result.applied_filters,
            confidence=gen_result.confidence,
            rewrite_applied=retrieval_result.rewrite_applied,
            rerank_applied=retrieval_result.rerank_applied,
            warnings=warnings,
            timing=RAGTiming(
                rewrite_ms=retrieval_timing.rewrite_ms,
                retrieval_ms=retrieval_timing.retrieval_ms,
                rerank_ms=retrieval_timing.rerank_ms,
                generation_ms=generation_ms,
                total_ms=_elapsed_ms(t0),
            ),
            generation_meta=gen_result.generation_meta,
            error=None,
        )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------
def _elapsed_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _error_result(
    request: RAGRequest,
    error: ErrorItem,
    *,
    retrieval_timing: RetrievalTiming | None,
    t0: float,
) -> RAGResult:
    rt = retrieval_timing or RetrievalTiming()
    return RAGResult(
        contract_version=RAG_CONTRACT_VERSION,
        trace_id=request.trace_id,
        status=RAGStatus.error,
        answer="系统暂时无法处理您的请求，请稍后重试。",
        facts=[],
        sources=[],
        evidence=[],
        applied_filters=request.filters,
        confidence=None,
        rewrite_applied=False,
        rerank_applied=False,
        warnings=[],
        timing=RAGTiming(
            rewrite_ms=rt.rewrite_ms,
            retrieval_ms=rt.retrieval_ms,
            rerank_ms=rt.rerank_ms,
            total_ms=_elapsed_ms(t0),
        ),
        generation_meta=GenerationMeta(),
        error=error,
    )
