"""Protocol interfaces for the RAG runtime — B, D, E depend on these, never on
concrete implementations.

Follows the same ``@runtime_checkable`` Protocol pattern as
``backend/repositories/protocols.py``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.schemas.rag_contract import (
    RAGRequest,
    RAGResult,
    RetrievalRequest,
    RetrievalResult,
)


@runtime_checkable
class RetrievalGateway(Protocol):
    """Gateway to D's retrieval service.

    Called by ``RagService`` — B never calls D directly.  Implementations
    wrap Chroma / the retrieval pipeline without exposing its internals.
    """

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...


@runtime_checkable
class GenerationClient(Protocol):
    """Generates answer content from structured facts and retrieved evidence.

    In production this wraps an LLM call.  In tests a Fake provides
    deterministic output so we never hit a real model.
    """

    async def generate(self, request: RAGRequest, retrieval: RetrievalResult) -> RAGResult: ...
