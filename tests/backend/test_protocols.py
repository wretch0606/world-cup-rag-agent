"""Protocol contract tests — both providers satisfy the same interface."""

from __future__ import annotations

from backend.repositories.protocols import FrontendDataProvider


def test_mock_provider_satisfies_protocol(mock_provider) -> None:
    assert isinstance(mock_provider, FrontendDataProvider)


def test_sqlite_provider_satisfies_protocol(sqlite_provider) -> None:
    assert isinstance(sqlite_provider, FrontendDataProvider)


def test_providers_return_same_shape(mock_provider, sqlite_provider) -> None:
    """Both providers return filter-options with the same top-level keys."""
    mock_opts = mock_provider.get_filter_options()
    sqlite_opts = sqlite_provider.get_filter_options()
    expected_keys = {"tournaments", "teams", "stages", "result_types", "data_status"}
    assert expected_keys.issubset(mock_opts.keys())
    assert expected_keys.issubset(sqlite_opts.keys())


def test_providers_filter_options_teams_have_ids(mock_provider, sqlite_provider) -> None:
    for prov in (mock_provider, sqlite_provider):
        opts = prov.get_filter_options()
        for team in opts["teams"]:
            assert "team_id" in team
            assert "name" in team
            assert team["team_id"].startswith("team_")
