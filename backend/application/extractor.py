"""Natural-language condition extractor for exact-fact queries.

Extracts: year, team_id, opponent_id, stage, result_type, has_penalties, match_id.
Rules-based (no LLM), deterministic.
"""

from __future__ import annotations

import re

from backend.schemas.common import StageEnum

# Match year patterns like "2022", "2018年"
_YEAR_RE = re.compile(r"(19\d{2}|20\d{2})\s*年?")
# Stage keywords → StageEnum value
_STAGE_MAP: dict[str, str] = {
    "决赛": "final",
    "半决赛": "semi_final",
    "三四名决赛": "third_place",
    "三四名": "third_place",
    "季军": "third_place",
    "1/4决赛": "quarter_final",
    "四分之一决赛": "quarter_final",
    "1/8决赛": "round_of_16",
    "八分之一决赛": "round_of_16",
    "小组赛": "group",
    "淘汰赛": "",  # too broad — don't bind to a single stage
}
# Penalty/point keywords
_PENALTY_KW = re.compile(r"点球")
# Match ID pattern
_MATCH_ID_RE = re.compile(r"M-\d{4}-\d{1,3}")


def extract(query: str) -> dict:
    """Extract structured conditions from a Chinese natural-language query.

    Returns a dict with keys: years, team_ids, stages, has_penalties, match_ids.
    """
    result: dict = {
        "years": [],
        "team_ids": [],
        "stages": [],
        "has_penalties": None,
        "match_ids": [],
    }

    # Years
    years = [int(m.group(1)) for m in _YEAR_RE.finditer(query)]
    result["years"] = list(dict.fromkeys(years))  # dedup, preserve order

    # Stages
    for kw, val in _STAGE_MAP.items():
        if kw in query and val:
            result["stages"].append(val)
    result["stages"] = list(dict.fromkeys(result["stages"]))

    # has_penalties
    if _PENALTY_KW.search(query):
        result["has_penalties"] = True

    # Match IDs
    result["match_ids"] = _MATCH_ID_RE.findall(query)

    # Team IDs — try to match from a known team map (loaded lazily)
    result["team_ids"] = _extract_team_ids(query)

    return result


# ------------------------------------------------------------------
# Team extraction — uses SQLite teams table at first call, caches
# ------------------------------------------------------------------
_team_index: dict[str, str] | None = None  # keyword → team_id


def _build_team_index() -> dict[str, str]:
    """Build a keyword→team_id index from the teams table (via SQLite provider if available)."""
    idx: dict[str, str] = {}
    try:
        # Try to load from actual DB or fall back to mock data
        from backend.config import settings

        if settings.frontend_data_mode == "sqlite" and settings.world_cup_db_path:
            from backend.repositories.sqlite_frontend_data import SQLiteFrontendDataProvider

            provider = SQLiteFrontendDataProvider(settings.world_cup_db_path)
            opts = provider.get_filter_options()
        else:
            from backend.repositories.mock_frontend_data import MockFrontendDataProvider

            provider = MockFrontendDataProvider()
            opts = provider.get_filter_options()
        for team in opts.get("teams", []):
            name = team.get("name", "")
            tid = team.get("team_id", "")
            # Index by full name
            idx[name] = tid
            # Index by common short forms
            short_map: dict[str, str] = {
                "阿根廷": "team_ARG",
                "法国": "team_FRA",
                "巴西": "team_BRA",
                "德国": "team_GER",
                "英格兰": "team_ENG",
                "英格兰队": "team_ENG",
                "西班牙": "team_ESP",
                "荷兰": "team_NED",
                "葡萄牙": "team_POR",
                "克罗地亚": "team_CRO",
                "摩洛哥": "team_MAR",
                "日本": "team_JPN",
                "韩国": "team_KOR",
                "意大利": "team_ITA",
                "乌拉圭": "team_URU",
                "比利时": "team_BEL",
                "墨西哥": "team_MEX",
                "美国": "team_USA",
                "哥伦比亚": "team_COL",
                "瑞典": "team_SWE",
                "俄罗斯": "team_RUS",
                "瑞士": "team_SUI",
                "丹麦": "team_DEN",
                "波兰": "team_POL",
                "塞内加尔": "team_SEN",
                "沙特": "team_KSA",
                "沙特阿拉伯": "team_KSA",
                "伊朗": "team_IRN",
                "澳大利亚": "team_AUS",
                "加纳": "team_GHA",
                "喀麦隆": "team_CMR",
                "突尼斯": "team_TUN",
                "哥斯达黎加": "team_CRC",
                "加拿大": "team_CAN",
                "塞尔维亚": "team_SRB",
                "威尔士": "team_WAL",
                "厄瓜多尔": "team_ECU",
                "卡塔尔": "team_QAT",
            }
            idx.update(short_map)
    except Exception:
        pass
    return idx


def _extract_team_ids(query: str) -> list[str]:
    """Find team_ids mentioned in the query by substring matching against known names."""
    global _team_index
    if _team_index is None:
        _team_index = _build_team_index()

    found: list[str] = []
    for name, tid in _team_index.items():
        if name in query:
            found.append(tid)
    return list(dict.fromkeys(found))
