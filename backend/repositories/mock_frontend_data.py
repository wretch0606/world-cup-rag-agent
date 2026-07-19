"""MockFrontendDataProvider — deterministic mock data for A↔B integration.

All responses marked data_status="mock". Uses a small set of self-consistent
matches (2022 final, 2022 semi, 2018 final, 2014 final).
"""

from __future__ import annotations

from backend.schemas.common import (
    MatchFilters,
    PaginatedMatches,
    RelationFilters,
    DocumentFilters,
)

# ---------------------------------------------------------------------------
# Self-consistent mock dataset (4 matches)
# ---------------------------------------------------------------------------
_MOCK_TEAMS: list[dict] = [
    {"team_id": "team_ARG", "name": "阿根廷"},
    {"team_id": "team_FRA", "name": "法国"},
    {"team_id": "team_CRO", "name": "克罗地亚"},
    {"team_id": "team_GER", "name": "德国"},
    {"team_id": "team_BRA", "name": "巴西"},
    {"team_id": "team_NED", "name": "荷兰"},
    {"team_id": "team_MAR", "name": "摩洛哥"},
]

_MOCK_TOURNAMENTS: list[dict] = [
    {"year": 2022, "label": "2022 卡塔尔世界杯", "host": "卡塔尔"},
    {"year": 2018, "label": "2018 俄罗斯世界杯", "host": "俄罗斯"},
    {"year": 2014, "label": "2014 巴西世界杯", "host": "巴西"},
]

_MOCK_MATCHES: list[dict] = [
    {
        "match_id": "M-2022-64",
        "tournament_year": 2022,
        "match_date": "2022-12-18",
        "stage": "final",
        "stage_name": "决赛",
        "home_team": {"team_id": "team_ARG", "name": "阿根廷"},
        "away_team": {"team_id": "team_FRA", "name": "法国"},
        "score": {
            "regular_time": {"home": 2, "away": 2},
            "after_extra_time": {"home": 3, "away": 3},
            "penalties": {"home": 4, "away": 2},
            "display": "3:3",
            "penalty_display": "4:2",
        },
        "result_type": "penalties",
        "winner_team": {"team_id": "team_ARG", "name": "阿根廷"},
    },
    {
        "match_id": "M-2022-61",
        "tournament_year": 2022,
        "match_date": "2022-12-13",
        "stage": "semi_final",
        "stage_name": "半决赛",
        "home_team": {"team_id": "team_ARG", "name": "阿根廷"},
        "away_team": {"team_id": "team_CRO", "name": "克罗地亚"},
        "score": {
            "regular_time": {"home": 3, "away": 0},
            "after_extra_time": None,
            "penalties": None,
            "display": "3:0",
            "penalty_display": None,
        },
        "result_type": "regulation",
        "winner_team": {"team_id": "team_ARG", "name": "阿根廷"},
    },
    {
        "match_id": "M-2018-64",
        "tournament_year": 2018,
        "match_date": "2018-07-15",
        "stage": "final",
        "stage_name": "决赛",
        "home_team": {"team_id": "team_FRA", "name": "法国"},
        "away_team": {"team_id": "team_CRO", "name": "克罗地亚"},
        "score": {
            "regular_time": {"home": 4, "away": 2},
            "after_extra_time": None,
            "penalties": None,
            "display": "4:2",
            "penalty_display": None,
        },
        "result_type": "regulation",
        "winner_team": {"team_id": "team_FRA", "name": "法国"},
    },
    {
        "match_id": "M-2022-44",
        "tournament_year": 2022,
        "match_date": "2022-12-01",
        "stage": "group",
        "stage_name": "小组赛",
        "home_team": {"team_id": "team_CRO", "name": "克罗地亚"},
        "away_team": {"team_id": "team_MAR", "name": "摩洛哥"},
        "score": {
            "regular_time": {"home": 0, "away": 0},
            "after_extra_time": None,
            "penalties": None,
            "display": "0:0",
            "penalty_display": None,
        },
        "result_type": "draw",
        "winner_team": None,
    },
    {
        "match_id": "M-2014-64",
        "tournament_year": 2014,
        "match_date": "2014-07-13",
        "stage": "final",
        "stage_name": "决赛",
        "home_team": {"team_id": "team_GER", "name": "德国"},
        "away_team": {"team_id": "team_ARG", "name": "阿根廷"},
        "score": {
            "regular_time": {"home": 0, "away": 0},
            "after_extra_time": {"home": 1, "away": 0},
            "penalties": None,
            "display": "1:0",
            "penalty_display": None,
        },
        "result_type": "extra_time",
        "winner_team": {"team_id": "team_GER", "name": "德国"},
    },
]


class MockFrontendDataProvider:
    """Deterministic mock data provider for A↔B frontend integration."""

    def __init__(self) -> None:
        self._matches: dict[str, dict] = {m["match_id"]: m for m in _MOCK_MATCHES}
        self._teams: dict[str, dict] = {t["team_id"]: t for t in _MOCK_TEAMS}

    # ------------------------------------------------------------------
    # FrontendDataProvider implementation
    # ------------------------------------------------------------------
    def get_filter_options(self) -> dict:
        stages = [
            {"value": "group", "label": "小组赛", "order": 10},
            {"value": "second_group", "label": "第二阶段小组赛", "order": 20},
            {"value": "round_of_16", "label": "1/8决赛", "order": 30},
            {"value": "quarter_final", "label": "1/4决赛", "order": 40},
            {"value": "semi_final", "label": "半决赛", "order": 50},
            {"value": "third_place", "label": "三四名决赛", "order": 60},
            {"value": "final_round", "label": "决赛循环赛", "order": 70},
            {"value": "final", "label": "决赛", "order": 80},
        ]
        result_types = [
            {"value": "regulation", "label": "常规时间决胜"},
            {"value": "extra_time", "label": "加时赛决胜"},
            {"value": "penalties", "label": "点球大战决胜"},
            {"value": "draw", "label": "平局"},
        ]
        return {
            "data_status": "mock",
            "tournaments": list(_MOCK_TOURNAMENTS),
            "teams": sorted(_MOCK_TEAMS, key=lambda t: t["name"]),
            "stages": stages,
            "result_types": result_types,
        }

    def list_matches(
        self, filters: MatchFilters, page: int = 1, page_size: int = 20
    ) -> PaginatedMatches:
        items = list(_MOCK_MATCHES)

        # Apply filters (mock — simple in-memory filtering)
        if filters.years:
            items = [m for m in items if m["tournament_year"] in filters.years]
        if filters.team_ids:
            items = [
                m
                for m in items
                if m["home_team"]["team_id"] in filters.team_ids
                or m["away_team"]["team_id"] in filters.team_ids
            ]
        if filters.stages:
            stage_values = [s.value if hasattr(s, "value") else s for s in filters.stages]
            items = [m for m in items if m["stage"] in stage_values]
        if filters.result_types:
            rt_values = [r.value if hasattr(r, "value") else r for r in filters.result_types]
            items = [m for m in items if m["result_type"] in rt_values]
        if filters.has_penalties is True:
            items = [m for m in items if m["result_type"] == "penalties"]

        total = len(items)
        start = (page - 1) * page_size
        paged = items[start : start + page_size]

        # Serialise filter values for applied_filters
        af: dict = {
            "years": filters.years,
            "team_ids": filters.team_ids,
            "stages": [s.value if hasattr(s, "value") else s for s in filters.stages],
            "result_types": [
                r.value if hasattr(r, "value") else r for r in filters.result_types
            ],
            "has_penalties": filters.has_penalties,
        }

        return PaginatedMatches(
            items=paged, total=total, page=page, page_size=page_size, applied_filters=af
        )

    def get_match(self, match_id: str) -> dict | None:
        match = self._matches.get(match_id)
        if match is None:
            return None
        result = dict(match)
        result["data_status"] = "mock"
        result["venue"] = "Mock Stadium"
        result["city"] = "Mock City"
        result["timeline"] = {"regular_time": [], "extra_time": [], "shootout": {"available": False, "home_score": 0, "away_score": 0, "events": [], "message": "Mock — no detailed event data"}}
        result["sources"] = [{"source_id": "src-mock-001", "title": "Frontend integration mock source", "url": None, "source_type": "mock", "data_version": "mock-v1", "used_for_fact_ids": []}]
        return result

    def get_team_relations(
        self, team_id: str, filters: RelationFilters, page: int = 1, page_size: int = 20
    ) -> dict:
        team = self._teams.get(team_id)
        if team is None:
            return {"team": None, "stats": {}, "matches": [], "graph": {"scope": "team_relations", "nodes": [], "edges": []}, "total": 0, "page": page, "page_size": page_size, "applied_filters": {}, "data_status": "mock"}
        # Find matches involving this team
        related = [m for m in _MOCK_MATCHES if m["home_team"]["team_id"] == team_id or m["away_team"]["team_id"] == team_id]
        # Apply filters
        if filters.year_from:
            related = [m for m in related if m["tournament_year"] >= filters.year_from]
        if filters.year_to:
            related = [m for m in related if m["tournament_year"] <= filters.year_to]
        if filters.opponent_id:
            related = [m for m in related if m["home_team"]["team_id"] == filters.opponent_id or m["away_team"]["team_id"] == filters.opponent_id]
        if filters.has_penalties is True:
            related = [m for m in related if m["result_type"] == "penalties"]
        # Build graph
        nodes_set: dict[str, dict] = {}
        edges: list[dict] = []
        for m in related:
            for t in (m["home_team"], m["away_team"]):
                nodes_set[t["team_id"]] = {"id": t["team_id"], "name": t["name"], "type": "team"}
            winner = m.get("winner_team")
            source = winner["team_id"] if winner else m["home_team"]["team_id"]
            target = m["away_team"]["team_id"] if winner and winner["team_id"] == m["home_team"]["team_id"] else (m["home_team"]["team_id"] if not winner else m["away_team"]["team_id"])
            if winner:
                target = m["away_team"]["team_id"] if winner["team_id"] == m["home_team"]["team_id"] else m["home_team"]["team_id"]
            else:
                source, target = m["home_team"]["team_id"], m["away_team"]["team_id"]
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
                "winner_team_id": winner["team_id"] if winner else None,
                "label": f"{m['tournament_year']} {m['stage_name']} {m['score']['display']}",
            })
        stats = {
            "matches": len(related),
            "regulation_or_extra_time_wins": 0,
            "draws": 0,
            "penalty_advances": 0,
            "losses": 0,
        }
        for m in related:
            w = m.get("winner_team")
            if w and w["team_id"] == team_id:
                if m["result_type"] == "penalties":
                    stats["penalty_advances"] += 1
                else:
                    stats["regulation_or_extra_time_wins"] += 1
            elif w and w["team_id"] != team_id:
                stats["losses"] += 1
            else:
                stats["draws"] += 1
        return {
            "data_status": "mock",
            "team": team,
            "stats": stats,
            "matches": related,
            "graph": {"scope": "team_relations", "nodes": list(nodes_set.values()), "edges": edges},
            "total": len(related),
            "page": page,
            "page_size": page_size,
            "applied_filters": {},
        }

    def list_documents(
        self, filters: DocumentFilters, page: int = 1, page_size: int = 20
    ) -> dict:
        return {
            "data_status": "mock",
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "applied_filters": {"status": filters.status, "data_version": filters.data_version},
        }
