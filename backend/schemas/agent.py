"""Agent Query DTOs — Pydantic v2, extra="forbid"."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentFilters(BaseModel):
    years: list[int] = Field(default_factory=list)
    team_ids: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    result_types: list[str] = Field(default_factory=list)
    match_ids: list[str] = Field(default_factory=list)
    has_penalties: bool | None = None

    model_config = {"extra": "forbid"}


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    filters: AgentFilters = Field(default_factory=AgentFilters)
    debug: bool = False

    model_config = {"extra": "forbid"}
