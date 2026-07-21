"""Application configuration via pydantic-settings."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application metadata
    app_name: str = "world-cup-rag-agent-backend"
    app_version: str = "0.1.0"
    app_description: str = "World Cup RAG Agent — FastAPI backend"

    # API
    api_prefix: str = "/api"

    # CORS — development defaults, override via env for production
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Data provider mode
    #   "mock"  — deterministic mock data for A↔B integration (all marked data_status=mock)
    #   "sqlite" — read-only SQLite; requires world_cup_db_path pointing to worldcup_v2.db
    frontend_data_mode: Literal["mock", "sqlite"] = "mock"
    world_cup_db_path: str = ""

    # Agent mode: deterministic mock responses or the LangGraph workflow
    agent_mode: Literal["mock", "langgraph"] = "mock"

    # Chroma retrieval
    chroma_data_dir: str = "./backend/data/chroma_db"
    embedding_mode: Literal["hash", "default", "bge"] = "default"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ------------------------------------------------------------------
    # RAG LLM — DeepSeek / OpenAI-compatible generation
    # ------------------------------------------------------------------
    rag_llm_base_url: str = "https://api.deepseek.com"
    rag_llm_api_key: str = ""
    rag_llm_model: str = "deepseek-v4-flash"
    rag_llm_timeout_ms: int = 30000
    rag_llm_max_tokens: int = 4096
    rag_llm_thinking: bool = False


settings = Settings()
