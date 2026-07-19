"""SQLiteFrontendDataProvider tests using fixture DB."""

from __future__ import annotations

from backend.repositories.sqlite_frontend_data import (
    SQLiteFrontendDataProvider,
    SQLiteFrontendProviderError,
)
from backend.schemas.common import MatchFilters
import sqlite3


def test_filter_options_live_data_status(sqlite_provider) -> None:
    opts = sqlite_provider.get_filter_options()
    assert opts["data_status"] == "live"


def test_filter_options_teams_sorted(sqlite_provider) -> None:
    opts = sqlite_provider.get_filter_options()
    names = [t["name"] for t in opts["teams"]]
    assert names == sorted(names)


def test_list_matches_default(sqlite_provider) -> None:
    result = sqlite_provider.list_matches(MatchFilters())
    assert result.total >= 5  # fixture has 6 matches


def test_list_matches_pagination(sqlite_provider) -> None:
    result = sqlite_provider.list_matches(MatchFilters(), page=1, page_size=3)
    assert len(result.items) <= 3
    assert result.page == 1


def test_list_matches_filter_by_team(sqlite_provider) -> None:
    result = sqlite_provider.list_matches(MatchFilters(team_ids=["team_ARG"]))
    for m in result.items:
        assert m["home_team"]["team_id"] == "team_ARG" or m["away_team"]["team_id"] == "team_ARG"


def test_list_matches_penalties_separate_score(sqlite_provider) -> None:
    result = sqlite_provider.list_matches(MatchFilters(has_penalties=True))
    if result.items:
        for m in result.items:
            assert m["result_type"] == "penalties"
            score = m["score"]
            assert score["penalties"] is not None
            assert score["penalty_display"] is not None
            assert score["display"] != score["penalty_display"]


def test_get_match_detail(sqlite_provider) -> None:
    match = sqlite_provider.get_match("M-2022-64")
    assert match is not None
    assert match["data_status"] == "live"
    assert match["home_team"]["team_id"] == "team_ARG"
    assert match["away_team"]["team_id"] == "team_FRA"
    assert match["score"]["regular_time"]["home"] == 2
    assert match["score"]["regular_time"]["away"] == 2
    assert match["score"]["penalties"]["home"] == 4
    assert match["score"]["penalties"]["away"] == 2


def test_get_match_extra_time_winner(sqlite_provider) -> None:
    match = sqlite_provider.get_match("M-2014-64")
    assert match is not None
    assert match["result_type"] == "extra_time"
    assert match["winner_team"] is not None
    assert match["winner_team"]["team_id"] == "team_GER"
    # after_extra_time must exist for extra_time matches
    assert match["score"]["after_extra_time"] is not None


def test_get_match_draw_no_winner(sqlite_provider) -> None:
    match = sqlite_provider.get_match("M-2022-44")
    assert match is not None
    assert match["result_type"] == "draw"
    assert match["winner_team"] is None


def test_get_match_unknown(sqlite_provider) -> None:
    assert sqlite_provider.get_match("M-9999-99") is None


def test_list_documents(sqlite_provider) -> None:
    result = sqlite_provider.list_documents(__import__("backend.schemas.common", fromlist=["DocumentFilters"]).DocumentFilters())
    assert result["data_status"] == "live"
    assert result["total"] >= 1


def test_sqlite_readonly(sqlite_provider) -> None:
    """Read-only constraint — writing should raise."""
    conn = sqlite_provider._connect()
    try:
        conn.execute("CREATE TABLE should_fail (x int)")
        assert False, "Should have raised"
    except sqlite3.OperationalError:
        pass  # expected
    finally:
        conn.close()


def test_missing_db_raises() -> None:
    try:
        SQLiteFrontendDataProvider("/nonexistent/path/db.sqlite")
        assert False, "Should have raised"
    except SQLiteFrontendProviderError:
        pass


