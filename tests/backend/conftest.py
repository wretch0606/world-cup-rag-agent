"""Shared fixtures for backend tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from backend.repositories.mock_frontend_data import MockFrontendDataProvider
from backend.repositories.sqlite_frontend_data import SQLiteFrontendDataProvider


# ---------------------------------------------------------------------------
# Fixture DB
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def fixture_db_path() -> str:
    """Create a small SQLite fixture DB covering all required scenarios."""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_FIXTURE_DDL)
    conn.executescript(_FIXTURE_DML)
    conn.commit()
    conn.close()
    yield db_path
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture()
def sqlite_provider(fixture_db_path: str) -> SQLiteFrontendDataProvider:
    return SQLiteFrontendDataProvider(fixture_db_path)


@pytest.fixture()
def mock_provider() -> MockFrontendDataProvider:
    return MockFrontendDataProvider()


# ---------------------------------------------------------------------------
# DDL / DML
# ---------------------------------------------------------------------------
_FIXTURE_DDL = """
CREATE TABLE tournaments (
    tournament_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    host TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    teams_count INTEGER
);

CREATE TABLE teams (
    team_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    aliases_json TEXT,
    confederation TEXT,
    fifa_code TEXT
);

CREATE TABLE matches (
    match_id TEXT PRIMARY KEY,
    tournament_year INTEGER NOT NULL,
    match_date TEXT NOT NULL,
    stage TEXT NOT NULL,
    group_name TEXT,
    venue TEXT,
    home_team_id TEXT NOT NULL,
    away_team_id TEXT NOT NULL,
    home_score_90 INTEGER NOT NULL,
    away_score_90 INTEGER NOT NULL,
    home_score_et INTEGER,
    away_score_et INTEGER,
    home_penalties INTEGER,
    away_penalties INTEGER,
    winner_team_id TEXT,
    result_type TEXT NOT NULL,
    score_display TEXT NOT NULL,
    penalty_score TEXT,
    source_id TEXT,
    data_version TEXT
);

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    title TEXT,
    source_url TEXT,
    source_type TEXT,
    retrieved_at TEXT,
    checksum TEXT,
    license_info TEXT,
    data_version TEXT
);

CREATE TABLE match_sources (
    match_id TEXT NOT NULL,
    source_id TEXT NOT NULL
);

CREATE TABLE goals (
    goal_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    player_id TEXT,
    family_name TEXT,
    given_name TEXT,
    shirt_number INTEGER,
    team_id TEXT,
    team_name TEXT,
    minute_label TEXT,
    minute_regulation INTEGER,
    minute_stoppage INTEGER,
    match_period TEXT,
    own_goal INTEGER,
    penalty INTEGER
);

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    title TEXT,
    source_id TEXT,
    file_path TEXT,
    file_type TEXT,
    parse_status TEXT,
    chunk_count INTEGER,
    parsed_at TEXT,
    data_version TEXT
);
"""

_FIXTURE_DML = """
INSERT INTO tournaments VALUES ('WC2022', 2022, '卡塔尔', '2022-11-20', '2022-12-18', 32);
INSERT INTO tournaments VALUES ('WC2018', 2018, '俄罗斯', '2018-06-14', '2018-07-15', 32);
INSERT INTO tournaments VALUES ('WC2014', 2014, '巴西', '2014-06-12', '2014-07-13', 32);

INSERT INTO teams VALUES ('team_ARG', '阿根廷', '["Argentina"]', 'CONMEBOL', 'ARG');
INSERT INTO teams VALUES ('team_FRA', '法国', '["France"]', 'UEFA', 'FRA');
INSERT INTO teams VALUES ('team_CRO', '克罗地亚', '["Croatia"]', 'UEFA', 'CRO');
INSERT INTO teams VALUES ('team_GER', '德国', '["Germany"]', 'UEFA', 'GER');
INSERT INTO teams VALUES ('team_MAR', '摩洛哥', '["Morocco"]', 'CAF', 'MAR');

-- 2022 Final (penalties)
INSERT INTO matches VALUES ('M-2022-64', 2022, '2022-12-18', 'final', NULL, 'Lusail Stadium',
    'team_ARG', 'team_FRA', 2, 2, 3, 3, 4, 2, 'team_ARG', 'penalties', '3:3', '4:2', NULL, NULL);
-- 2022 Semi (regulation)
INSERT INTO matches VALUES ('M-2022-61', 2022, '2022-12-13', 'semi_final', NULL, 'Lusail Stadium',
    'team_ARG', 'team_CRO', 3, 0, NULL, NULL, NULL, NULL, 'team_ARG', 'regulation', '3:0', NULL, NULL, NULL);
-- 2018 Final (regulation)
INSERT INTO matches VALUES ('M-2018-64', 2018, '2018-07-15', 'final', NULL, 'Luzhniki Stadium',
    'team_FRA', 'team_CRO', 4, 2, NULL, NULL, NULL, NULL, 'team_FRA', 'regulation', '4:2', NULL, NULL, NULL);
-- 2014 Final (extra_time)
INSERT INTO matches VALUES ('M-2014-64', 2014, '2014-07-13', 'final', NULL, 'Maracana',
    'team_GER', 'team_ARG', 0, 0, 1, 0, NULL, NULL, 'team_GER', 'extra_time', '1:0', NULL, NULL, NULL);
-- 2022 group stage draw (draw result type)
INSERT INTO matches VALUES ('M-2022-44', 2022, '2022-12-01', 'group', 'F组', 'Al Thumama Stadium',
    'team_CRO', 'team_MAR', 0, 0, NULL, NULL, NULL, NULL, NULL, 'draw', '0:0', NULL, NULL, NULL);
-- 1974 second_group stage
INSERT INTO matches VALUES ('M-1974-26', 1974, '1974-06-26', 'second_group', 'B组', 'Munich',
    'team_GER', 'team_ARG', 2, 0, NULL, NULL, NULL, NULL, 'team_GER', 'regulation', '2:0', NULL, NULL, NULL);

INSERT INTO sources VALUES ('src-001', 'Kaggle FIFA Dataset', 'https://www.kaggle.com/datasets/fifa-world-cup', 'csv', '2026-01-01', NULL, 'CC0', '2026-07-16-v2');
INSERT INTO sources VALUES ('src-002', 'Frontend integration mock source', NULL, 'mock', NULL, NULL, NULL, NULL);

INSERT INTO match_sources VALUES ('M-2022-64', 'src-001');
INSERT INTO match_sources VALUES ('M-2018-64', 'src-001');

INSERT INTO goals VALUES ('G-001', 'M-2022-64', NULL, 'Messi', 'Lionel', 10, 'team_ARG', '阿根廷', '23''', 23, 0, 'first_half', 0, 1);
INSERT INTO goals VALUES ('G-002', 'M-2022-64', NULL, 'Di Maria', 'Angel', 11, 'team_ARG', '阿根廷', '36''', 36, 0, 'first_half', 0, 0);
INSERT INTO goals VALUES ('G-003', 'M-2022-64', NULL, 'Mbappe', 'Kylian', 10, 'team_FRA', '法国', '80''', 80, 0, 'second_half', 0, 1);

INSERT INTO documents VALUES ('doc-001', 'FIFA World Cup Dataset', 'src-001', '/data/src-001.csv', 'csv', 'parsed', 964, '2026-07-16', '2026-07-16-v2');
"""
