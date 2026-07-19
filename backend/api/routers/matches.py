"""GET /api/matches — filtered, paginated match list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.common import MatchFilters, ResultTypeEnum, StageEnum
from backend.schemas.response import ApiResponse, error, ok
from backend.schemas.responses import MatchDetailData, MatchesData

router = APIRouter(tags=["matches"])


@router.get("/matches", response_model=ApiResponse[MatchesData])
async def list_matches(
    years: list[int] = Query(default_factory=list, description="世界杯年份"),
    team_ids: list[str] = Query(default_factory=list, description="球队 ID"),
    stages: list[str] = Query(default_factory=list, description="阶段枚举值"),
    result_types: list[str] = Query(default_factory=list, description="结果类型"),
    has_penalties: bool | None = Query(default=None, description="仅看点球大战的比赛"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return filtered + paginated match summaries for the timeline."""
    # Normalise has_penalties: False → None (no filter)
    hp = has_penalties if has_penalties is True else None

    # Parse stage enums
    parsed_stages: list[StageEnum] = []
    for s in stages:
        try:
            parsed_stages.append(StageEnum(s))
        except ValueError:
            pass  # ignore invalid stage values

    # Parse result type enums
    parsed_rts: list[ResultTypeEnum] = []
    for r in result_types:
        try:
            parsed_rts.append(ResultTypeEnum(r))
        except ValueError:
            pass

    filters = MatchFilters(
        years=years,
        team_ids=team_ids,
        stages=parsed_stages,
        result_types=parsed_rts,
        has_penalties=hp,
    )
    result = provider.list_matches(filters, page=page, page_size=page_size)
    response_data = result.model_dump()
    # Inject data_status from config
    from backend.config import settings as app_settings
    response_data["data_status"] = "live" if app_settings.frontend_data_mode == "sqlite" else "mock"
    return ok(data=response_data)


@router.get("/matches/{match_id}", response_model=ApiResponse[MatchDetailData])
async def get_match(
    match_id: str,
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return full match detail with timeline, events, and sources."""
    data = provider.get_match(match_id)
    if data is None:
        return error(
            code="MATCH_NOT_FOUND",
            message=f"未找到 match_id 为 {match_id} 的比赛",
            status_code=404,
            retryable=False,
        )
    return ok(data=data)
