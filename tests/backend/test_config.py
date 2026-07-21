"""Configuration regression tests."""

from pathlib import Path

from backend.config import Settings


def test_env_example_loads_cors_origins(monkeypatch) -> None:
    """The checked-in example must be directly consumable by pydantic-settings."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    env_example = Path(__file__).resolve().parents[2] / ".env.example"

    example_settings = Settings(_env_file=env_example)

    assert example_settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert example_settings.chroma_data_dir == "data/generated/chroma_demo"
    assert example_settings.embedding_mode == "hash"
