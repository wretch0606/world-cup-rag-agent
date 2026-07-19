"""GET /api/teams/{team_id}/relations — team head-to-head and stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.common import RelationFilters
from backend.schemas.response import ApiResponse, error, ok
from backend.schemas.responses import TeamRelationsData

router = APIRouter(tags=["teams"])


@router.get("/teams/{team_id}/relations", response_model=ApiResponse[TeamRelationsData])
async def get_team_relations(
    team_id: str,
    year_from: int | None = Query(default=None, description="起始年份"),
    year_to: int | None = Query(default=None, description="结束年份"),
    opponent_id: str | None = Query(default=None, description="指定对手 team_id"),
    stages: list[str] = Query(default_factory=list, description="阶段枚举值"),
    result_types: list[str] = Query(default_factory=list, description="结果类型"),
    has_penalties: bool | None = Query(default=None, description="仅看点球大战"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return team relation stats, match list, and head-to-head graph."""
    hp = has_penalties if has_penalties is True else None

    from backend.schemas.common import StageEnum

    parsed_stages: list[StageEnum] = []
    for s in stages:
        try:
            parsed_stages.append(StageEnum(s))
        except ValueError:
            pass

    filters = RelationFilters(
        year_from=year_from,
        year_to=year_to,
        opponent_id=opponent_id,
        stages=parsed_stages,
        result_types=[],
        has_penalties=hp,
    )
    data = provider.get_team_relations(team_id, filters, page=page, page_size=page_size)

    if data.get("team") is None:
        return error(
            code="TEAM_NOT_FOUND",
            message=f"未找到 team_id 为 {team_id} 的球队",
            status_code=404,
            retryable=False,
        )
    return ok(data=data)
