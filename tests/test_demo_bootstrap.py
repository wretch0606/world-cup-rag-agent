"""Integration tests for the offline SQLite live-demo bootstrap."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BOOTSTRAP_SCRIPT = ROOT_DIR / "scripts" / "init_demo_data.py"


def test_demo_bootstrap_is_repeatable(tmp_path: Path) -> None:
    command = [sys.executable, str(BOOTSTRAP_SCRIPT), "--output-dir", str(tmp_path)]

    first = subprocess.run(command, cwd=ROOT_DIR, check=True, capture_output=True, text=True)
    second = subprocess.run(command, cwd=ROOT_DIR, check=True, capture_output=True, text=True)

    database = tmp_path / "worldcup_demo.db"
    facts_path = tmp_path / "demo_match_facts.jsonl"
    report_path = tmp_path / "demo_cleaning_report.json"
    chroma_path = tmp_path / "chroma_demo" / "chroma.sqlite3"

    assert database.exists()
    assert facts_path.exists()
    assert report_path.exists()
    assert chroma_path.exists()
    assert "FRONTEND_DATA_MODE=sqlite" in first.stdout
    assert "AGENT_MODE=langgraph" in second.stdout
    assert "Chroma live-demo data is ready" in first.stdout
    assert "top match: M-2022-001" in second.stdout
    assert "gateway status: ok" in second.stdout
    assert "Offline API demo is ready" in first.stdout
    assert "hybrid query: degraded (trusted offline generation)" in second.stdout

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 1
        final_score = connection.execute(
            """SELECT home_score_90, away_score_90, home_score_et, away_score_et,
                      home_penalties, away_penalties
               FROM matches
               WHERE tournament_year = 2022 AND stage = 'final'"""
        ).fetchone()

    assert final_score == (2, 2, 3, 3, 4, 2)
    assert len(facts_path.read_text(encoding="utf-8").splitlines()) == 6
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"] == {
        "total_records": 6,
        "valid": 6,
        "fixed": 6,
        "rejected": 0,
    }
