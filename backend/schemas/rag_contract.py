"""Shared RAG runtime contract models — single source of truth for B, D, E.

Contract version: rag-v1.1-draft

These models are internal to the B→E→D→E→B pipeline.  Frontend-facing
DTOs live in ``backend/schemas/common.py`` and ``responses.py``.

Do NOT import provider-specific or database-internal modules here.
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# Reused from the frontend API contract — single source of truth for enums
from backend.schemas.common import ResultTypeEnum, StageEnum  # noqa: F401

# ---------------------------------------------------------------------------
# Canonical contract version — tests and docs reference this constant
# ---------------------------------------------------------------------------
RAG_CONTRACT_VERSION: str = "rag-v1.1-draft"


# ---------------------------------------------------------------------------
# RAG-specific enums (not in common.py)
# ---------------------------------------------------------------------------
class QueryTypeEnum(StrEnum):
    semantic = "semantic"
    hybrid = "hybrid"


class RAGStatus(StrEnum):
    ok = "ok"
    empty = "empty"
    degraded = "degraded"
    error = "error"


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------
class RetrievalFilters(BaseModel):
    """Hard constraints that B normalises and passes to E→D unchanged."""

    years: list[int] = Field(default_factory=list)
    team_ids: list[str] = Field(default_factory=list)
    stages: list[StageEnum] = Field(default_factory=list)
    result_types: list[ResultTypeEnum] = Field(default_factory=list)
    match_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class StructuredFact(BaseModel):
    """A single match-level fact resolved by B via SQLite (exact path)."""

    match_id: str
    match_date: date | None = None
    tournament_year: int
    stage: StageEnum
    stage_name: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    home_score_90: int | None = None
    away_score_90: int | None = None
    home_score_et: int | None = None
    away_score_et: int | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None
    score_display: str
    penalty_score: str | None = None
    result_type: ResultTypeEnum
    winner_team_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_result_type_constraints(self) -> StructuredFact:
        if self.result_type == ResultTypeEnum.penalties and self.penalty_score is None:
            raise ValueError("penalty_score is required when result_type is 'penalties'")
        if self.result_type == ResultTypeEnum.draw and self.winner_team_id is not None:
            raise ValueError("winner_team_id must be null when result_type is 'draw'")
        return self


class SourceItem(BaseModel):
    """Canonical source reference — absorbs fields from generation-v2.0.

    This model is used across the RAG pipeline.  The frontend-facing
    ``backend.schemas.common.SourceItem`` is a separate DTO for the A↔B API.
    """

    source_id: str
    title: str
    url: str | None = None
    page: int | None = None
    document_id: str | None = None
    data_version: str | None = None
    used_for_fact_ids: list[str] = Field(default_factory=list)
    # -- generation-v2.0 extended fields (optional, do not fabricate) --
    source_type: str | None = None
    publisher: str | None = None
    retrieved_at: str | None = None

    model_config = {"extra": "forbid"}


class RAGOptions(BaseModel):
    """Retrieval and generation tuning knobs."""

    retrieval_top_k: int = Field(default=10, ge=1, le=50)
    rerank_top_n: int = Field(default=5, ge=1, le=50)
    use_query_rewrite: bool = False
    use_reranker: bool = False
    min_rerank_score: float | None = None
    timeout_ms: int = Field(default=8000, ge=1000, le=30000)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_rerank_bound(self) -> RAGOptions:
        if self.rerank_top_n > self.retrieval_top_k:
            raise ValueError(
                f"rerank_top_n ({self.rerank_top_n}) must be <= "
                f"retrieval_top_k ({self.retrieval_top_k})"
            )
        return self


# ---------------------------------------------------------------------------
# B → E request
# ---------------------------------------------------------------------------
class RAGRequest(BaseModel):
    """B passes this to E for semantic / hybrid queries."""

    contract_version: str
    trace_id: str
    question: str
    original_question: str
    query_type: QueryTypeEnum
    filters: RetrievalFilters
    structured_facts: list[StructuredFact] = Field(default_factory=list)
    source_catalog: list[SourceItem] = Field(default_factory=list)
    options: RAGOptions

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# E → D request
# ---------------------------------------------------------------------------
class RetrievalRequest(BaseModel):
    """E forwards B's hard constraints to D unchanged."""

    contract_version: str
    trace_id: str
    query: str
    original_question: str
    filters: RetrievalFilters
    options: RAGOptions

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# D → E response
# ---------------------------------------------------------------------------
class EvidenceItem(BaseModel):
    """A single retrieval candidate returned by D."""

    chunk_id: str
    document_id: str
    collection: str | None = None
    match_id: str | None = None
    source_id: str
    document_name: str
    source_url: str | None = None
    source_page: int | None = None
    text: str
    language: str | None = None
    data_version: str
    chunk_index: int | None = None
    vector_distance: float | None = None
    rerank_score: float | None = None
    retrieval_rank: int | None = None
    rerank_rank: int | None = None

    model_config = {"extra": "forbid"}


class RetrievalTiming(BaseModel):
    rewrite_ms: int = 0
    retrieval_ms: int = 0
    rerank_ms: int = 0
    total_ms: int = 0

    model_config = {"extra": "forbid"}


class WarningItem(BaseModel):
    code: str
    message: str
    component: str
    retryable: bool = False

    model_config = {"extra": "forbid"}


class ErrorItem(BaseModel):
    code: str
    message: str
    component: str
    retryable: bool = False
    detail_id: str | None = None

    model_config = {"extra": "forbid"}


class RetrievalResult(BaseModel):
    """D returns this to E after query-rewrite → Chroma → reranker."""

    contract_version: str
    trace_id: str
    status: RAGStatus
    original_query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    items: list[EvidenceItem] = Field(default_factory=list)
    applied_filters: RetrievalFilters
    rewrite_applied: bool = False
    rerank_applied: bool = False
    warnings: list[WarningItem] = Field(default_factory=list)
    timing: RetrievalTiming = Field(default_factory=RetrievalTiming)
    error: ErrorItem | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_status_error_consistency(self) -> RetrievalResult:
        if self.status == RAGStatus.error and self.error is None:
            raise ValueError("error is required when status is 'error'")
        if self.status != RAGStatus.error and self.error is not None:
            raise ValueError("error must be null when status is not 'error'")
        return self


# ---------------------------------------------------------------------------
# E → B: discriminated fact union
# ---------------------------------------------------------------------------
class MatchResultFact(BaseModel):
    fact_type: Literal["match_result"] = "match_result"
    fact_id: str
    match_id: str
    tournament_year: int
    stage: StageEnum
    stage_name: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    score_display: str
    penalty_score: str | None = None
    result_type: ResultTypeEnum
    winner_team_id: str | None = None
    text: str
    source_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_result_type_constraints(self) -> MatchResultFact:
        if self.result_type == ResultTypeEnum.penalties and self.penalty_score is None:
            raise ValueError("penalty_score is required when result_type is 'penalties'")
        if self.result_type == ResultTypeEnum.draw and self.winner_team_id is not None:
            raise ValueError("winner_team_id must be null when result_type is 'draw'")
        return self


class RelationFact(BaseModel):
    fact_type: Literal["relation"] = "relation"
    fact_id: str
    team_ids: list[str] = Field(default_factory=list)
    opponent_ids: list[str] = Field(default_factory=list)
    match_ids: list[str] = Field(default_factory=list)
    text: str
    source_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class SummaryFact(BaseModel):
    fact_type: Literal["summary"] = "summary"
    fact_id: str
    match_ids: list[str] = Field(default_factory=list)
    tournament_years: list[int] = Field(default_factory=list)
    text: str
    source_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


RAGFact = Annotated[
    MatchResultFact | RelationFact | SummaryFact,
    Field(discriminator="fact_type"),
]


# ---------------------------------------------------------------------------
# E → B: full generation result
# ---------------------------------------------------------------------------
class RAGTiming(BaseModel):
    rewrite_ms: int = 0
    retrieval_ms: int = 0
    rerank_ms: int = 0
    generation_ms: int = 0
    total_ms: int = 0

    model_config = {"extra": "forbid"}


class GenerationMeta(BaseModel):
    prompt_name: str | None = None
    prompt_version: str | None = None
    model_name: str | None = None
    confidence_method: str | None = None

    model_config = {"extra": "forbid"}


class RAGResult(BaseModel):
    """E returns this to B after fact-fusion → LLM generation."""

    contract_version: str
    trace_id: str
    status: RAGStatus
    answer: str
    facts: list[RAGFact] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    applied_filters: RetrievalFilters
    confidence: float | None = None
    rewrite_applied: bool = False
    rerank_applied: bool = False
    warnings: list[WarningItem] = Field(default_factory=list)
    timing: RAGTiming = Field(default_factory=RAGTiming)
    generation_meta: GenerationMeta = Field(default_factory=GenerationMeta)
    error: ErrorItem | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_confidence_range(self) -> RAGResult:
        if self.confidence is not None and not (0 <= self.confidence <= 1):
            raise ValueError(
                f"confidence must be in [0, 1] when set, got {self.confidence}"
            )
        return self

    @model_validator(mode="after")
    def _check_status_error_consistency(self) -> RAGResult:
        if self.status == RAGStatus.error and self.error is None:
            raise ValueError("error is required when status is 'error'")
        if self.status != RAGStatus.error and self.error is not None:
            raise ValueError("error must be null when status is not 'error'")
        return self

    @model_validator(mode="after")
    def _check_trace_id_trailing_whitespace(self) -> RAGResult:
        """Reject trace_id values that differ only in trailing whitespace.

        This is a defence-in-depth check: contract_version is validated
        separately in tests against the expected literal ``rag-v1.1-draft``.
        """
        if self.trace_id != self.trace_id.rstrip():
            raise ValueError("trace_id must not end with whitespace")
        return self
