"""Mapper unit tests — field normalisation rules."""

from __future__ import annotations

from backend.repositories.mapper import build_match_summary, build_score_breakdown


def test_regular_time_only() -> None:
    breakdown = build_score_breakdown({
        "home_score_90": 3, "away_score_90": 0,
        "home_score_et": None, "away_score_et": None,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": None, "score_display": "3:0",
    })
    assert breakdown.regular_time.home == 3
    assert breakdown.regular_time.away == 0
    assert breakdown.after_extra_time is None
    assert breakdown.penalties is None
    assert breakdown.penalty_display is None


def test_extra_time_produces_after_extra_time() -> None:
    breakdown = build_score_breakdown({
        "home_score_90": 0, "away_score_90": 0,
        "home_score_et": 1, "away_score_et": 0,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": None, "score_display": "1:0",
    })
    assert breakdown.after_extra_time is not None
    assert breakdown.after_extra_time.home == 1
    assert breakdown.after_extra_time.away == 0
    assert breakdown.penalties is None


def test_penalties() -> None:
    breakdown = build_score_breakdown({
        "home_score_90": 2, "away_score_90": 2,
        "home_score_et": 3, "away_score_et": 3,
        "home_penalties": 4, "away_penalties": 2,
        "penalty_score": "4:2", "score_display": "3:3",
    })
    assert breakdown.penalties is not None
    assert breakdown.penalties.home == 4
    assert breakdown.penalties.away == 2
    assert breakdown.penalty_display == "4:2"
    assert breakdown.display == "3:3"


def test_empty_penalty_score_string_normalised() -> None:
    """penalty_score='' must become penalties=null."""
    breakdown = build_score_breakdown({
        "home_score_90": 2, "away_score_90": 1,
        "home_score_et": None, "away_score_et": None,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": "", "score_display": "2:1",
    })
    assert breakdown.penalties is None
    assert breakdown.penalty_display is None


def test_winner_null_not_inferred() -> None:
    """winner_team_id empty → winner=null, even for extra_time."""
    summary = build_match_summary({
        "match_id": "M-TEST", "tournament_year": 1974,
        "match_date": "1974-06-26", "stage": "final_round",
        "home_team_id": "team_A", "home_team_name": "A",
        "away_team_id": "team_B", "away_team_name": "B",
        "home_score_90": 1, "away_score_90": 1,
        "home_score_et": None, "away_score_et": None,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": None, "score_display": "1:1",
        "result_type": "extra_time", "winner_team_id": "",
        "winner_team_name": "",
    })
    assert summary["winner_team"] is None


def test_second_group_stage_preserved() -> None:
    summary = build_match_summary({
        "match_id": "M-TEST2", "tournament_year": 1974,
        "match_date": "1974-06-26", "stage": "second_group",
        "home_team_id": "team_A", "home_team_name": "A",
        "away_team_id": "team_B", "away_team_name": "B",
        "home_score_90": 2, "away_score_90": 0,
        "home_score_et": None, "away_score_et": None,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": None, "score_display": "2:0",
        "result_type": "regulation", "winner_team_id": "team_A",
        "winner_team_name": "A",
    })
    assert summary["stage"] == "second_group"
    assert summary["stage_name"] == "第二阶段小组赛"


def test_final_round_stage_preserved() -> None:
    summary = build_match_summary({
        "match_id": "M-TEST3", "tournament_year": 1950,
        "match_date": "1950-07-16", "stage": "final_round",
        "home_team_id": "team_A", "home_team_name": "A",
        "away_team_id": "team_B", "away_team_name": "B",
        "home_score_90": 2, "away_score_90": 1,
        "home_score_et": None, "away_score_et": None,
        "home_penalties": None, "away_penalties": None,
        "penalty_score": None, "score_display": "2:1",
        "result_type": "regulation", "winner_team_id": "team_A",
        "winner_team_name": "A",
    })
    assert summary["stage"] == "final_round"
    assert summary["stage_name"] == "决赛循环赛"
