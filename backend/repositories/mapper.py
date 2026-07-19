"""Field normalisation mapper — converts raw DB rows into public DTOs.

Rules (v2.0 plan §6.2):
  - penalty_score=""  → penalties=null, penalty_display=null
  - home_score_et / away_score_et both empty → after_extra_time=null
  - winner_team_id empty → winner_team=null (never infer from result_type)
  - stage second_group / final_round kept as-is
"""

from __future__ import annotations

from typing import Any

from backend.schemas.common import (
    ExtraTimeScore,
    PenaltyScore,
    RegularTimeScore,
    ScoreBreakdown,
    StageEnum,
    TeamRef,
)


def _int_or_none(val: Any) -> int | None:
    """Coerce a database value to int, returning None for empty/None."""
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    return int(val)


def _norm_stage(raw: str | None) -> str:
    """Normalise a stage value to the StageEnum contract."""
    if not raw:
        return "group"
    # C database sometimes has "决赛循环赛" or "决赛" etc.
    mapping: dict[str, str] = {
        "决赛": "final",
        "决赛循环赛": "final_round",
        "半决赛": "semi_final",
        "三四名决赛": "third_place",
        "1/4决赛": "quarter_final",
        "1/8决赛": "round_of_16",
        "小组赛": "group",
        "第二阶段小组赛": "second_group",
    }
    return mapping.get(raw, raw)


def build_score_breakdown(row: dict[str, Any]) -> ScoreBreakdown:
    """Build a ScoreBreakdown from a raw match row, applying all normalisation rules."""
    home_90 = _int_or_none(row.get("home_score_90", 0)) or 0
    away_90 = _int_or_none(row.get("away_score_90", 0)) or 0

    home_et = _int_or_none(row.get("home_score_et"))
    away_et = _int_or_none(row.get("away_score_et"))

    home_pen = _int_or_none(row.get("home_penalties"))
    away_pen = _int_or_none(row.get("away_penalties"))

    # penalty_score="" normalisation
    penalty_score_raw = row.get("penalty_score")
    if penalty_score_raw is not None and str(penalty_score_raw).strip() == "":
        penalty_score_raw = None

    # After extra time
    after_extra: ExtraTimeScore | None = None
    if home_et is not None and away_et is not None:
        after_extra = ExtraTimeScore(home=home_et, away=away_et)

    # Penalties
    penalties: PenaltyScore | None = None
    penalty_display: str | None = None
    if home_pen is not None and away_pen is not None:
        penalties = PenaltyScore(home=home_pen, away=away_pen)
        penalty_display = str(penalty_score_raw) if penalty_score_raw else f"{home_pen}:{away_pen}"
    elif penalty_score_raw is not None:
        # Parse "4:2" style display
        parts = str(penalty_score_raw).split(":")
        if len(parts) == 2:
            try:
                penalties = PenaltyScore(home=int(parts[0]), away=int(parts[1]))
                penalty_display = str(penalty_score_raw)
            except ValueError:
                pass

    # Display score
    score_display_raw = row.get("score_display", "")
    display = str(score_display_raw) if score_display_raw else f"{home_90}:{away_90}"

    return ScoreBreakdown(
        regular_time=RegularTimeScore(home=home_90, away=away_90),
        after_extra_time=after_extra,
        penalties=penalties,
        display=display,
        penalty_display=penalty_display,
    )


def build_team_ref(row: dict[str, Any], prefix: str) -> TeamRef:
    """Build a TeamRef from prefixed columns (e.g. prefix='home_', 'away_')."""
    team_id = row.get(f"{prefix}team_id", "")
    name = row.get(f"{prefix}team_name") or row.get(f"{prefix}name") or ""
    return TeamRef(team_id=str(team_id), name=str(name))


def build_match_summary(row: dict[str, Any]) -> dict:
    """Build a match summary dict (for list endpoints) from a raw row."""
    from backend.schemas.common import ResultTypeEnum

    result_type_raw = row.get("result_type", "regulation")
    try:
        result_type = ResultTypeEnum(result_type_raw)
    except ValueError:
        result_type = ResultTypeEnum.regulation

    winner_raw = row.get("winner_team_id")
    winner: dict | None = None
    if winner_raw and str(winner_raw).strip():
        winner_name = row.get("winner_team_name") or row.get("winner_name") or ""
        winner = TeamRef(team_id=str(winner_raw), name=str(winner_name)).model_dump()

    stage_raw = row.get("stage", "group")
    stage = _norm_stage(stage_raw)
    try:
        stage_enum = StageEnum(stage)
        stage_name = stage_enum.label
    except ValueError:
        stage_name = stage_raw

    return {
        "match_id": str(row.get("match_id", "")),
        "tournament_year": int(row.get("tournament_year", 0)),
        "match_date": str(row.get("match_date", "")),
        "stage": stage,
        "stage_name": stage_name,
        "home_team": build_team_ref(row, "home_").model_dump(),
        "away_team": build_team_ref(row, "away_").model_dump(),
        "score": build_score_breakdown(row).model_dump(),
        "result_type": result_type.value,
        "winner_team": winner,
    }
