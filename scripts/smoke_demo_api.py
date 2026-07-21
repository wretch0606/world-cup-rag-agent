"""Validate the offline demo through the public FastAPI query endpoint."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
DEFAULT_DB_PATH = ROOT_DIR / "data" / "generated" / "worldcup_demo.db"
DEFAULT_CHROMA_DIR = ROOT_DIR / "data" / "generated" / "chroma_demo"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test the offline demo through FastAPI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--chroma-dir", type=Path, default=DEFAULT_CHROMA_DIR)
    args = parser.parse_args(argv)

    database = args.database.resolve()
    chroma_dir = args.chroma_dir.resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Demo database not found: {database}")
    if not (chroma_dir / "chroma.sqlite3").is_file():
        raise FileNotFoundError(f"Demo Chroma store not found: {chroma_dir}")

    os.environ.update(
        {
            "FRONTEND_DATA_MODE": "sqlite",
            "WORLD_CUP_DB_PATH": str(database),
            "AGENT_MODE": "langgraph",
            "CHROMA_DATA_DIR": str(chroma_dir),
            "EMBEDDING_MODE": "hash",
            "RAG_GENERATION_MODE": "offline",
            "RAG_LLM_API_KEY": "",
        }
    )

    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    exact = _query(client, "2022年世界杯决赛比分是多少？")
    hybrid = _query(client, "介绍2022年世界杯决赛的重要情节")
    semantic = _query(client, "回顾世界杯经典比赛")

    _validate_exact(exact)
    _validate_hybrid(hybrid)
    _validate_semantic(semantic)

    print("\nOffline API demo is ready:")
    print("  exact query: ok")
    print("  hybrid query: degraded (trusted offline generation)")
    print("  semantic query: degraded (trusted offline generation)")
    print("  top match: M-2022-001")
    return 0


def _query(client, question: str) -> dict:
    response = client.post("/api/agent/query", json={"question": question, "filters": {}})
    if response.status_code != 200:
        raise RuntimeError(f"Demo API request failed ({response.status_code}): {response.text}")
    payload = response.json()
    if payload.get("success") is not True or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"Unexpected Demo API envelope: {payload}")
    return payload["data"]


def _validate_exact(data: dict) -> None:
    if data.get("status") != "ok" or data.get("route") != "structured_query":
        raise RuntimeError(f"Exact demo query failed: {data}")
    if not data.get("facts") or data["facts"][0].get("match_id") != "M-2022-001":
        raise RuntimeError(f"Exact demo fact missing: {data}")


def _validate_hybrid(data: dict) -> None:
    if data.get("status") != "degraded" or data.get("route") != "hybrid_query":
        raise RuntimeError(f"Hybrid demo query failed: {data}")
    if "系统暂时无法处理" in data.get("answer", ""):
        raise RuntimeError(f"Hybrid demo returned an error answer: {data}")
    if "OFFLINE_GENERATION" not in {item.get("code") for item in data.get("warnings", [])}:
        raise RuntimeError(f"Hybrid demo did not disclose offline generation: {data}")

    fact = data.get("facts", [{}])[0]
    if fact.get("match_id") != "M-2022-001":
        raise RuntimeError(f"Hybrid demo returned the wrong match: {data}")
    if fact.get("home_team", {}).get("team_id") != "team_ARG":
        raise RuntimeError(f"Hybrid demo lost the home-team mapping: {data}")
    if fact.get("score", {}).get("regular_time") != {"home": 2, "away": 2}:
        raise RuntimeError(f"Hybrid demo lost the score mapping: {data}")


def _validate_semantic(data: dict) -> None:
    if data.get("status") != "degraded" or data.get("route") != "rag_query":
        raise RuntimeError(f"Semantic demo query failed: {data}")
    facts = data.get("facts", [])
    if not facts or facts[0].get("fact_type") != "summary":
        raise RuntimeError(f"Semantic demo summary missing: {data}")
    if not data.get("sources"):
        raise RuntimeError(f"Semantic demo sources missing: {data}")


if __name__ == "__main__":
    raise SystemExit(main())
