"""Application configuration via pydantic-settings."""

from __future__ import annotations

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

    # CORS — development defaults, override via env for production
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
