"""GET /api/graph — D3.js graph data derived from match list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.common import MatchFilters, ResultTypeEnum, StageEnum
from backend.schemas.response import ApiResponse, ok

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=ApiResponse[dict])
async def get_graph(
    years: list[int] = Query(default_factory=list, description="世界杯年份"),
    team_ids: list[str] = Query(default_factory=list, description="球队 ID"),
    stages: list[str] = Query(default_factory=list, description="阶段枚举值"),
    result_types: list[str] = Query(default_factory=list, description="结果类型"),
    has_penalties: bool | None = Query(default=None, description="仅看点球大战的比赛"),
    limit: int = Query(default=100, ge=1, le=500, description="最大边数"),
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return D3 graph (nodes + edges) derived from filtered match list."""
    hp = has_penalties if has_penalties is True else None

    parsed_stages: list[StageEnum] = []
    for s in stages:
        try:
            parsed_stages.append(StageEnum(s))
        except ValueError:
            pass

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
    # Fetch matches — same source as /api/matches
    result = provider.list_matches(filters, page=1, page_size=limit)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    truncated = result.total > limit

    for m in result.items[:limit]:
        hid = m["home_team"]["team_id"]
        aid = m["away_team"]["team_id"]
        nodes[hid] = {"id": hid, "name": m["home_team"]["name"], "type": "team"}
        nodes[aid] = {"id": aid, "name": m["away_team"]["name"], "type": "team"}

        w = m.get("winner_team")
        score_display = m.get("score", {}).get("display", "")
        source = w["team_id"] if w else hid
        target = aid if (w and w["team_id"] == hid) else (hid if not w else hid)
        edges.append({
            "id": f"edge-{m['match_id']}",
            "source": source,
            "target": target,
            "type": "match_result",
            "match_id": m["match_id"],
            "tournament_year": m["tournament_year"],
            "stage": m["stage"],
            "stage_name": m["stage_name"],
            "result_type": m["result_type"],
            "winner_team_id": w["team_id"] if w else None,
            "label": f"{m['tournament_year']} {m['stage_name']} {score_display}",
        })

    af: dict = {
        "years": filters.years,
        "team_ids": filters.team_ids,
        "stages": [s.value if hasattr(s, "value") else s for s in filters.stages],
        "result_types": [r.value if hasattr(r, "value") else r for r in filters.result_types],
        "has_penalties": filters.has_penalties,
    }

    # data_status inherited from provider result
    ds = result.items[0].get("data_status", "mock") if result.items else "mock" if not hasattr(provider, "_db_path") else "live"

    return ok(data={
        "data_status": ds,
        "scope": "filtered_matches",
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {"node_count": len(nodes), "edge_count": len(edges), "truncated": truncated},
        "applied_filters": af,
    })
