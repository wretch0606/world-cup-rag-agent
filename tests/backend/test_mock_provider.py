"""MockFrontendDataProvider tests."""

from __future__ import annotations

from backend.schemas.common import MatchFilters


def test_filter_options_data_status_mock(mock_provider) -> None:
    opts = mock_provider.get_filter_options()
    assert opts["data_status"] == "mock"


def test_filter_options_has_8_stages(mock_provider) -> None:
    opts = mock_provider.get_filter_options()
    assert len(opts["stages"]) == 8
    stage_values = [s["value"] for s in opts["stages"]]
    assert "second_group" in stage_values
    assert "final_round" in stage_values


def test_list_matches_returns_all_with_no_filters(mock_provider) -> None:
    result = mock_provider.list_matches(MatchFilters())
    assert result.total == 5
    assert len(result.items) == 5


def test_list_matches_filter_by_year(mock_provider) -> None:
    result = mock_provider.list_matches(MatchFilters(years=[2022]))
    assert result.total == 3


def test_list_matches_filter_has_penalties(mock_provider) -> None:
    result = mock_provider.list_matches(MatchFilters(has_penalties=True))
    assert result.total == 1
    assert result.items[0]["match_id"] == "M-2022-64"


def test_get_match_returns_detail(mock_provider) -> None:
    match = mock_provider.get_match("M-2022-64")
    assert match is not None
    assert match["data_status"] == "mock"
    assert match["score"]["penalties"] is not None
    assert match["score"]["penalty_display"] == "4:2"


def test_get_match_unknown_returns_none(mock_provider) -> None:
    assert mock_provider.get_match("M-9999-99") is None


def test_team_relations_returns_stats(mock_provider) -> None:
    result = mock_provider.get_team_relations("team_ARG", __import__("backend.schemas.common", fromlist=["RelationFilters"]).RelationFilters())
    assert result["team"]["team_id"] == "team_ARG"
    assert result["stats"]["matches"] > 0


def test_documents_empty(mock_provider) -> None:
    result = mock_provider.list_documents(__import__("backend.schemas.common", fromlist=["DocumentFilters"]).DocumentFilters())
    assert result["data_status"] == "mock"
    assert result["items"] == []
    assert result["total"] == 0
