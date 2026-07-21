"""Regression tests for the shared data-pipeline entities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.entities import CleaningReport, Match, Team


def test_entity_to_dict_returns_json_ready_data() -> None:
    team = Team(team_id="team_FRA", canonical_name="法国", aliases=["France", "FRA"])

    assert team.to_dict() == {
        "team_id": "team_FRA",
        "canonical_name": "法国",
        "aliases": ["France", "FRA"],
        "confederation": "",
        "fifa_code": "",
    }


def test_mutable_defaults_are_not_shared() -> None:
    first = Team(team_id="team_FRA", canonical_name="法国")
    second = Team(team_id="team_ARG", canonical_name="阿根廷")

    first.aliases.append("France")

    assert second.aliases == []


def test_match_defaults_follow_v2_contract() -> None:
    match = Match(
        match_id="M-2022-64",
        tournament_year=2022,
        match_date="2022-12-18",
        stage="final",
        home_team_id="team_ARG",
        away_team_id="team_FRA",
        home_score_90=2,
        away_score_90=2,
        result_type="penalties",
        score_display="3:3",
    )

    assert match.data_version == "2026-07-16-v2"
    assert match.home_score_et is None
    assert match.winner_team_id is None


def test_cleaning_report_tracks_actions_and_serializes_summary() -> None:
    report = CleaningReport(total_records=2)
    report.add_warning("M-1", "stage", "Final", "normalized:Final->final")
    report.add_error("M-2", "invalid score", field="home_score_90", value="-1")

    assert report.to_dict() == {
        "summary": {
            "total_records": 2,
            "valid": 0,
            "fixed": 1,
            "rejected": 1,
        },
        "warnings": [
            {
                "match_id": "M-1",
                "field": "stage",
                "value": "Final",
                "action": "normalized:Final->final",
            }
        ],
        "errors": [
            {
                "match_id": "M-2",
                "message": "invalid score",
                "field": "home_score_90",
                "value": "-1",
            }
        ],
    }
