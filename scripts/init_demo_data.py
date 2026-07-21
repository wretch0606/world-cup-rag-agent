"""Build the repository's offline SQLite live-demo dataset.

The full 964-match source CSV is intentionally not committed. This command uses
the checked-in six-match 2022 sample so a fresh clone can exercise the real
SQLite provider and exact-query LangGraph path without network access or API
keys.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT_DIR / "data-pipeline"
IMPORT_SCRIPT = PIPELINE_DIR / "scripts" / "import_data_v2.py"
SAMPLE_INPUT = PIPELINE_DIR / "raw_data" / "matches_2022_sample.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "generated"

ARTIFACT_NAMES = {
    "db": "worldcup_demo.db",
    "facts_jsonl": "demo_match_facts.jsonl",
    "facts_json": "demo_match_facts.json",
    "report": "demo_cleaning_report.json",
}


def build_demo_data(output_dir: Path) -> dict[str, Path]:
    """Build, validate, and publish the live-demo artifacts."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".sqlite-demo-", dir=output_dir) as temp_name:
        temp_dir = Path(temp_name)
        staged = {key: temp_dir / name for key, name in ARTIFACT_NAMES.items()}

        command = [
            sys.executable,
            str(IMPORT_SCRIPT),
            "--input",
            str(SAMPLE_INPUT),
            "--source_type",
            "json",
            "--year",
            "2022",
            "--db",
            str(staged["db"]),
            "--output-facts",
            str(staged["facts_jsonl"]),
            "--output-facts-json",
            str(staged["facts_json"]),
            "--output-report",
            str(staged["report"]),
        ]
        subprocess.run(command, cwd=ROOT_DIR, check=True)
        _validate_artifacts(staged)

        published = {key: output_dir / name for key, name in ARTIFACT_NAMES.items()}
        for key, source in staged.items():
            source.replace(published[key])

    return published


def _validate_artifacts(artifacts: dict[str, Path]) -> None:
    """Reject incomplete builds before they replace a working demo dataset."""
    connection = sqlite3.connect(artifacts["db"])
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("tournaments", "teams", "matches", "sources", "match_sources")
        }
        final_score = connection.execute(
            """SELECT home_score_90, away_score_90, home_score_et, away_score_et,
                      home_penalties, away_penalties
               FROM matches
               WHERE tournament_year = 2022 AND stage = 'final'"""
        ).fetchone()
    finally:
        connection.close()

    expected_counts = {
        "tournaments": 22,
        "teams": 85,
        "matches": 6,
        "sources": 5,
        "match_sources": 12,
    }
    if counts != expected_counts:
        raise RuntimeError(f"Unexpected demo database counts: {counts}")
    if final_score != (2, 2, 3, 3, 4, 2):
        raise RuntimeError(f"Unexpected 2022 final score breakdown: {final_score}")

    fact_lines = [
        json.loads(line)
        for line in artifacts["facts_jsonl"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(fact_lines) != expected_counts["matches"]:
        raise RuntimeError(f"Expected 6 demo facts, found {len(fact_lines)}")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the offline SQLite live-demo dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated database and fact files",
    )
    args = parser.parse_args(argv)

    artifacts = build_demo_data(args.output_dir)
    db_path = _display_path(artifacts["db"])

    print("\nSQLite live-demo data is ready:")
    for path in artifacts.values():
        print(f"  - {_display_path(path)}")
    print("\nSet these values in .env before starting the backend:")
    print("  FRONTEND_DATA_MODE=sqlite")
    print(f"  WORLD_CUP_DB_PATH={db_path}")
    print("  AGENT_MODE=langgraph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
