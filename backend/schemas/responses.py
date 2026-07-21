"""Concrete Pydantic response DTOs — one per API endpoint, for OpenAPI typing."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Health ──
class HealthData(BaseModel):
    status: str = "ok"
    service: str = "world-cup-rag-agent-backend"
    version: str = "0.1.0"
    python: str = "3.12"
    model_config = {"extra": "ignore"}


# ── Filter Options ──
class TournamentOption(BaseModel):
    year: int
    label: str
    host: str | None = None
    model_config = {"extra": "ignore"}


class TeamOption(BaseModel):
    team_id: str
    name: str
    model_config = {"extra": "ignore"}


class StageOption(BaseModel):
    value: str
    label: str
    order: int
    model_config = {"extra": "ignore"}


class ResultTypeOption(BaseModel):
    value: str
    label: str
    model_config = {"extra": "ignore"}


class FilterOptionsData(BaseModel):
    data_status: str = "mock"
    tournaments: list[TournamentOption] = Field(default_factory=list)
    teams: list[TeamOption] = Field(default_factory=list)
    stages: list[StageOption] = Field(default_factory=list)
    result_types: list[ResultTypeOption] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


# ── Matches ──
class TeamRef(BaseModel):
    team_id: str
    name: str
    model_config = {"extra": "ignore"}


class RegularTimeScore(BaseModel):
    home: int
    away: int


class ExtraTimeScore(BaseModel):
    home: int
    away: int


class PenaltyScore(BaseModel):
    home: int
    away: int


class ScoreBreakdown(BaseModel):
    regular_time: RegularTimeScore
    after_extra_time: ExtraTimeScore | None = None
    penalties: PenaltyScore | None = None
    display: str
    penalty_display: str | None = None
    model_config = {"extra": "ignore"}


class MatchSummary(BaseModel):
    match_id: str
    tournament_year: int
    match_date: str
    stage: str
    stage_name: str
    home_team: TeamRef
    away_team: TeamRef
    score: ScoreBreakdown
    result_type: str
    winner_team: TeamRef | None = None
    model_config = {"extra": "ignore"}


class MatchesData(BaseModel):
    data_status: str = "mock"
    items: list[MatchSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    applied_filters: dict = Field(default_factory=dict)
    model_config = {"extra": "ignore"}


# ── Match Detail ──
class ShootoutInfo(BaseModel):
    available: bool = False
    home_score: int = 0
    away_score: int = 0
    events: list = Field(default_factory=list)
    message: str = ""


class Timeline(BaseModel):
    regular_time: list = Field(default_factory=list)
    extra_time: list = Field(default_factory=list)
    shootout: ShootoutInfo = Field(default_factory=ShootoutInfo)


class SourceItem(BaseModel):
    source_id: str
    title: str
    url: str | None = None
    page: int | None = None
    document_id: str | None = None
    data_version: str | None = None
    used_for_fact_ids: list[str] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class MatchDetailData(BaseModel):
    data_status: str = "mock"
    match_id: str = ""
    tournament_year: int = 0
    match_date: str = ""
    stage: str = ""
    stage_name: str = ""
    venue: str | None = None
    city: str | None = None
    home_team: TeamRef | None = None
    away_team: TeamRef | None = None
    score: ScoreBreakdown | None = None
    result_type: str = ""
    winner_team: TeamRef | None = None
    timeline: Timeline = Field(default_factory=Timeline)
    sources: list[SourceItem] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


# ── Graph ──
class GraphNode(BaseModel):
    id: str
    name: str
    type: str = "team"
    model_config = {"extra": "ignore"}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "match_result"
    match_id: str
    tournament_year: int
    stage: str
    stage_name: str
    result_type: str
    winner_team_id: str | None = None
    label: str
    model_config = {"extra": "ignore"}


class GraphStats(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    truncated: bool = False


class GraphData(BaseModel):
    data_status: str = "mock"
    scope: str = "filtered_matches"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)
    applied_filters: dict = Field(default_factory=dict)
    model_config = {"extra": "ignore"}


# ── Documents ──
class DocumentItem(BaseModel):
    document_id: str
    title: str
    source_id: str
    file_type: str = ""
    parse_status: str = ""
    chunk_count: int = 0
    parsed_at: str | None = None
    data_version: str = ""
    model_config = {"extra": "ignore"}


class DocumentsData(BaseModel):
    data_status: str = "mock"
    items: list[DocumentItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    applied_filters: dict = Field(default_factory=dict)
    model_config = {"extra": "ignore"}


# ── Team Relations ──
class TeamStats(BaseModel):
    matches: int = 0
    regulation_or_extra_time_wins: int = 0
    draws: int = 0
    penalty_advances: int = 0
    losses: int = 0


class TeamRelationsData(BaseModel):
    data_status: str = "mock"
    team: TeamRef | None = None
    stats: TeamStats = Field(default_factory=TeamStats)
    matches: list[MatchSummary] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    total: int = 0
    page: int = 1
    page_size: int = 20
    applied_filters: dict = Field(default_factory=dict)
    model_config = {"extra": "ignore"}


# ── Agent Query ──
class AgentFact(BaseModel):
    fact_type: str = ""
    fact_id: str = ""
    match_id: str | None = None
    tournament_year: int | None = None
    stage: str | None = None
    stage_name: str | None = None
    home_team: TeamRef | None = None
    away_team: TeamRef | None = None
    score: ScoreBreakdown | None = None
    result_type: str | None = None
    winner_team: TeamRef | None = None
    text: str = ""
    source_ids: list[str] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class AgentWarning(BaseModel):
    code: str = ""
    message: str = ""
    component: str = ""
    retryable: bool = False


class AgentTiming(BaseModel):
    routing_ms: int = 0
    sql_ms: int = 0
    retrieval_ms: int = 0
    generation_ms: int = 0
    total_ms: int = 0


class AgentQueryData(BaseModel):
    data_status: str = "mock"
    status: str = "ok"
    intent: str = ""
    route: str = ""
    answer: str = ""
    needs_clarification: bool = False
    clarification_question: str | None = None
    facts: list[AgentFact] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    applied_filters: dict = Field(default_factory=dict)
    confidence: float | None = None
    warnings: list[AgentWarning] = Field(default_factory=list)
    timing: AgentTiming = Field(default_factory=AgentTiming)
    model_config = {"extra": "ignore"}


# ── Error Response (for OpenAPI 422) ──
class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    code: str = "VALIDATION_ERROR"
    message: str = "请求参数校验失败"
    data: None = None
    trace_id: str = ""
    timestamp: str = ""
    retryable: bool = False
    details: list[ErrorDetail] = Field(default_factory=list)
    model_config = {"extra": "ignore"}
