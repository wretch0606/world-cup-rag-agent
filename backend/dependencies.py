"""FastAPI dependency injection — selects provider based on settings."""

from __future__ import annotations

import logging

from backend.config import settings
from backend.repositories.mock_frontend_data import MockFrontendDataProvider
from backend.repositories.protocols import FrontendDataProvider
from backend.repositories.sqlite_frontend_data import (
    SQLiteFrontendDataProvider,
    SQLiteFrontendProviderError,
)

logger = logging.getLogger("backend.dependencies")

# Module-level singleton — created once at import time
_data_provider: FrontendDataProvider | None = None


def _build_provider() -> FrontendDataProvider:
    """Instantiate the configured data provider."""
    mode = settings.frontend_data_mode
    if mode == "sqlite":
        logger.info("Initialising SQLiteFrontendDataProvider (read-only)")
        return SQLiteFrontendDataProvider(settings.world_cup_db_path)
    logger.info("Initialising MockFrontendDataProvider (mock data)")
    return MockFrontendDataProvider()


def get_provider() -> FrontendDataProvider:
    """Return the configured FrontendDataProvider singleton.

    If the SQLite provider fails to initialise (missing DB), raises a
    clear diagnostic rather than silently falling back to mock.
    """
    global _data_provider
    if _data_provider is None:
        try:
            _data_provider = _build_provider()
        except SQLiteFrontendProviderError:
            logger.exception("SQLite provider initialisation failed")
            raise
    return _data_provider


# ---------------------------------------------------------------------------
# Agent service
# ---------------------------------------------------------------------------
_agent_service: object | None = None


def get_agent_service() -> object:
    """Return the configured AgentService singleton (mock or langgraph)."""
    global _agent_service
    if _agent_service is None:
        mode = settings.agent_mode
        if mode == "langgraph":
            from backend.application.langgraph_agent_service import LangGraphAgentService

            logger.info("Initialising LangGraphAgentService")
            _agent_service = LangGraphAgentService()
        else:
            from backend.application.mock_agent_service import MockAgentService

            logger.info("Initialising MockAgentService")
            _agent_service = MockAgentService()
    return _agent_service
