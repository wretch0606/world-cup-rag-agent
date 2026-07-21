"""Shared public DTOs for the A↔B HTTP API contract.

These models are used by ALL providers and routers — do NOT put
provider-specific or database-internal fields here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class StageEnum(StrEnum):
    group = "group"
    second_group = "second_group"
    round_of_16 = "round_of_16"
    quarter_final = "quarter_final"
    semi_final = "semi_final"
    third_place = "third_place"
    final_round = "final_round"
    final = "final"

    @property
    def label(self) -> str:
        _labels: dict[str, str] = {
            "group": "小组赛",
            "second_group": "第二阶段小组赛",
            "round_of_16": "1/8决赛",
            "quarter_final": "1/4决赛",
            "semi_final": "半决赛",
            "third_place": "三四名决赛",
            "final_round": "决赛循环赛",
            "final": "决赛",
        }
        return _labels[self.value]

    @property
    def order(self) -> int:
        _order: dict[str, int] = {
            "group": 10,
            "second_group": 20,
            "round_of_16": 30,
            "quarter_final": 40,
            "semi_final": 50,
            "third_place": 60,
            "final_round": 70,
            "final": 80,
        }
        return _order[self.value]


class ResultTypeEnum(StrEnum):
    regulation = "regulation"
    extra_time = "extra_time"
    penalties = "penalties"
    draw = "draw"


class AgentStatusEnum(StrEnum):
    ok = "ok"
    empty = "empty"
    degraded = "degraded"
    clarification_required = "clarification_required"
    error = "error"


class IntentEnum(StrEnum):
    general_chat = "general_chat"
    match_result_query = "match_result_query"
    match_relation_query = "match_relation_query"
    summary_query = "summary_query"
    comparison_query = "comparison_query"
    role_chat = "role_chat"
    out_of_scope = "out_of_scope"


class RouteEnum(StrEnum):
    general_chat = "general_chat"
    structured_query = "structured_query"
    rag_query = "rag_query"
    hybrid_query = "hybrid_query"
    role_agent = "role_agent"
    clarification = "clarification"


class DataStatusEnum(StrEnum):
    live = "live"
    mock = "mock"
    degraded = "degraded"


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------
class TeamRef(BaseModel):
    team_id: str
    name: str

    model_config = {"extra": "forbid"}


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

    model_config = {"extra": "forbid"}


class SourceItem(BaseModel):
    source_id: str
    title: str
    url: str | None = None
    page: int | None = None
    document_id: str | None = None
    data_version: str | None = None
    used_for_fact_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class WarningItem(BaseModel):
    code: str
    message: str
    component: str
    retryable: bool = False

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Paging / filters
# ---------------------------------------------------------------------------
class MatchFilters(BaseModel):
    years: list[int] = Field(default_factory=list)
    team_ids: list[str] = Field(default_factory=list)
    stages: list[StageEnum] = Field(default_factory=list)
    result_types: list[ResultTypeEnum] = Field(default_factory=list)
    has_penalties: bool | None = None

    model_config = {"extra": "forbid"}


class RelationFilters(BaseModel):
    year_from: int | None = None
    year_to: int | None = None
    opponent_id: str | None = None
    stages: list[StageEnum] = Field(default_factory=list)
    result_types: list[ResultTypeEnum] = Field(default_factory=list)
    has_penalties: bool | None = None

    model_config = {"extra": "forbid"}


class DocumentFilters(BaseModel):
    status: str | None = None  # pending / parsed / failed
    data_version: str | None = None

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Paginated wrapper
# ---------------------------------------------------------------------------
class PaginatedMatches(BaseModel):
    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    applied_filters: dict = Field(default_factory=dict)
