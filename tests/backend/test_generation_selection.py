"""Runtime generation-client selection tests."""

from __future__ import annotations

from backend.application.langgraph_agent_service import _build_generation_client
from backend.config import settings
from backend.rag.offline_generation import OfflineEvidenceGenerationClient
from backend.rag.openai_compatible_generation import OpenAICompatibleGenerationClient


def test_auto_mode_uses_offline_generation_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_generation_mode", "auto")
    monkeypatch.setattr(settings, "rag_llm_api_key", "")

    assert isinstance(_build_generation_client(), OfflineEvidenceGenerationClient)


def test_auto_mode_uses_llm_when_api_key_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_generation_mode", "auto")
    monkeypatch.setattr(settings, "rag_llm_api_key", "test-key")

    assert isinstance(_build_generation_client(), OpenAICompatibleGenerationClient)


def test_explicit_offline_mode_wins_even_with_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_generation_mode", "offline")
    monkeypatch.setattr(settings, "rag_llm_api_key", "test-key")

    assert isinstance(_build_generation_client(), OfflineEvidenceGenerationClient)
