"""Provider protocols — Router depends on these, never on concrete implementations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.schemas.common import (
    DocumentFilters,
    MatchFilters,
    PaginatedMatches,
    RelationFilters,
)


@runtime_checkable
class FrontendDataProvider(Protocol):
    """Read-only data provider for filter-options, matches, relations, graph, documents.

    Implementations: MockFrontendDataProvider, SQLiteFrontendDataProvider.
    """

    def get_filter_options(self) -> dict:
        """Return tournaments, teams, stages, result_types for the left sidebar."""
        ...

    def list_matches(
        self, filters: MatchFilters, page: int = 1, page_size: int = 20
    ) -> PaginatedMatches:
        """Return filtered + paginated match summaries."""
        ...

    def get_match(self, match_id: str) -> dict | None:
        """Return full match detail, or None if not found."""
        ...

    def get_team_relations(
        self, team_id: str, filters: RelationFilters, page: int = 1, page_size: int = 20
    ) -> dict:
        """Return team relation stats, matches, and graph."""
        ...

    def list_documents(
        self, filters: DocumentFilters, page: int = 1, page_size: int = 20
    ) -> dict:
        """Return registered/indexed documents and their parse status."""
        ...


@runtime_checkable
class AgentService(Protocol):
    """Agent query service — MockAgentService or LangGraphAgentService (future)."""

    def query(self, request: dict, trace_id: str) -> dict:
        """Return AgentQueryResponse data dict."""
        ...
