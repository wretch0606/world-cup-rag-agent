"""
SQLite 数据库操作层 v2

提供建表、CRUD、查询等所有数据库操作。
支持 v2 schema 的所有新增表：team_aliases, match_sources, import_jobs, audit_logs, documents。
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

from models.entities import (
    Tournament, Team, TeamAlias, Match, Source, MatchSource,
    Goal, StructuredFact, ImportJob, AuditLog,
)


# ═══════════════════════════════════════════════════════════
#  建表
# ═══════════════════════════════════════════════════════════

def create_tables(db_path: str, schema_file: str) -> None:
    """执行 schema.sql 中的所有建表语句。"""
    conn = sqlite3.connect(db_path)
    try:
        schema = Path(schema_file).read_text(encoding="utf-8")
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    """获取数据库连接，启用外键和 WAL 模式。"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ═══════════════════════════════════════════════════════════
#  Tournament
# ═══════════════════════════════════════════════════════════

def insert_tournament(db_path: str, t: Tournament) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO tournaments
               (tournament_id, year, host, host_en, start_date, end_date,
                teams_count, champion, top_scorer, top_scorer_goals)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.tournament_id, t.year, t.host, t.host_en,
             t.start_date, t.end_date, t.teams_count,
             t.champion, t.top_scorer, t.top_scorer_goals),
        )
        conn.commit()
    finally:
        conn.close()


def import_tournaments_from_json(db_path: str, json_file: str) -> int:
    """从 tournaments.json 批量导入全部 22 届。返回导入数量。"""
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for t_data in data.get("tournaments", {}).values():
        t = Tournament(**{k: v for k, v in t_data.items()
                          if k in Tournament.__dataclass_fields__})
        insert_tournament(db_path, t)
        count += 1
    return count


def query_tournament_by_year(db_path: str, year: int) -> Optional[dict]:
    """按年份查询 tournament。"""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tournaments WHERE year = ?", (year,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_all_tournaments(db_path: str) -> list[dict]:
    """查询全部 tournament 记录。"""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tournaments ORDER BY year"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  Team
# ═══════════════════════════════════════════════════════════

def insert_team(db_path: str, t: Team) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO teams
               (team_id, canonical_name, aliases_json, confederation, fifa_code)
               VALUES (?, ?, ?, ?, ?)""",
            (t.team_id, t.canonical_name, json.dumps(t.aliases, ensure_ascii=False),
             t.confederation, t.fifa_code),
        )
        conn.commit()
    finally:
        conn.close()


def import_teams_from_aliases(db_path: str, alias_file: str) -> int:
    """从别名映射文件批量导入球队。返回导入的球队数。"""
    with open(alias_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    teams_data = data.get("teams", {})
    count = 0
    for team_id, info in teams_data.items():
        t = Team(
            team_id=team_id,
            canonical_name=info.get("canonical_name", team_id),
            confederation=info.get("confederation", ""),
            fifa_code=info.get("fifa_code", ""),
        )
        insert_team(db_path, t)
        count += 1
    return count


def query_all_teams(db_path: str) -> list[Team]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM teams").fetchall()
        teams = []
        for row in rows:
            aliases = json.loads(row["aliases_json"]) if row["aliases_json"] else []
            teams.append(Team(
                team_id=row["team_id"],
                canonical_name=row["canonical_name"],
                aliases=aliases,
                confederation=row["confederation"] or "",
                fifa_code=row["fifa_code"] or "",
            ))
        return teams
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  TeamAlias
# ═══════════════════════════════════════════════════════════

def import_team_aliases(db_path: str, alias_file: str) -> int:
    """从别名文件导入独立 team_aliases 表。返回导入的别名条数。"""
    with open(alias_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    aliases_data = data.get("aliases", {})
    team_info = data.get("teams", {})
    count = 0

    conn = get_connection(db_path)
    try:
        for alias_text, team_id in aliases_data.items():
            normalized = alias_text.lower().strip()
            language = "zh" if any('一' <= c <= '鿿' for c in alias_text) else "en"
            alias_type = "fifa_code" if len(alias_text) == 3 and alias_text.isupper() else "full_name"

            conn.execute(
                """INSERT OR REPLACE INTO team_aliases
                   (team_id, alias, language, alias_type, normalized_alias)
                   VALUES (?, ?, ?, ?, ?)""",
                (team_id, alias_text, language, alias_type, normalized),
            )
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


# ═══════════════════════════════════════════════════════════
#  Match
# ═══════════════════════════════════════════════════════════

def insert_match(db_path: str, m: Match) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO matches
               (match_id, tournament_id, tournament_year, match_date,
                raw_match_date, stage, stage_name, group_name, venue, city,
                home_team_id, away_team_id,
                home_score_90, away_score_90,
                home_score_et, away_score_et,
                home_penalties, away_penalties,
                winner_team_id, result_type, score_display, penalty_score,
                data_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (m.match_id, m.tournament_id, m.tournament_year, m.match_date,
             m.raw_match_date, m.stage, m.stage_name, m.group_name, m.venue, m.city,
             m.home_team_id, m.away_team_id,
             m.home_score_90, m.away_score_90,
             m.home_score_et, m.away_score_et,
             m.home_penalties, m.away_penalties,
             m.winner_team_id, m.result_type, m.score_display, m.penalty_score,
             m.data_version),
        )
        conn.commit()
    finally:
        conn.close()


def bulk_insert_matches(db_path: str, matches: list[Match]) -> int:
    """批量导入比赛记录（单个事务）。返回导入条数。"""
    if not matches:
        return 0

    conn = get_connection(db_path)
    try:
        sql = """INSERT OR REPLACE INTO matches
                 (match_id, tournament_id, tournament_year, match_date,
                  raw_match_date, stage, stage_name, group_name, venue, city,
                  home_team_id, away_team_id,
                  home_score_90, away_score_90,
                  home_score_et, away_score_et,
                  home_penalties, away_penalties,
                  winner_team_id, result_type, score_display, penalty_score,
                  data_version)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        data = [
            (m.match_id, m.tournament_id, m.tournament_year, m.match_date,
             m.raw_match_date, m.stage, m.stage_name, m.group_name, m.venue, m.city,
             m.home_team_id, m.away_team_id,
             m.home_score_90, m.away_score_90,
             m.home_score_et, m.away_score_et,
             m.home_penalties, m.away_penalties,
             m.winner_team_id, m.result_type, m.score_display, m.penalty_score,
             m.data_version)
            for m in matches
        ]
        conn.executemany(sql, data)
        conn.commit()
        return len(data)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  Source
# ═══════════════════════════════════════════════════════════

def insert_source(db_path: str, s: Source) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO sources
               (source_id, title, source_url, source_type, publisher,
                retrieved_at, checksum, license_info, data_version, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s.source_id, s.title, s.source_url, s.source_type, s.publisher,
             s.retrieved_at, s.checksum, s.license_info, s.data_version, s.description),
        )
        conn.commit()
    finally:
        conn.close()


def import_sources_from_manifest(db_path: str, manifest_file: str) -> int:
    """从 source_manifest.json 导入全部来源。返回导入数量。"""
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for s_data in data.get("sources", []):
        s = Source(**{k: v for k, v in s_data.items()
                      if k in Source.__dataclass_fields__})
        insert_source(db_path, s)
        count += 1
    return count


# ═══════════════════════════════════════════════════════════
#  MatchSource（多对多关联）
# ═══════════════════════════════════════════════════════════

def insert_match_source(db_path: str, ms: MatchSource) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO match_sources
               (match_id, source_id, evidence_type, is_primary, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (ms.match_id, ms.source_id, ms.evidence_type, ms.is_primary, ms.notes),
        )
        conn.commit()
    finally:
        conn.close()


def query_sources_by_match(db_path: str, match_id: str) -> list[dict]:
    """查询某场比赛的全部来源。"""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """SELECT s.*, ms.evidence_type, ms.is_primary, ms.notes
               FROM sources s
               JOIN match_sources ms ON s.source_id = ms.source_id
               WHERE ms.match_id = ?
               ORDER BY ms.is_primary DESC""",
            (match_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  ImportJob
# ═══════════════════════════════════════════════════════════

def insert_import_job(db_path: str, job: ImportJob) -> int:
    """记录导入任务，返回 job_id。"""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO import_jobs
               (job_type, source_file, records_total, records_valid,
                records_fixed, records_rejected, started_at, completed_at,
                data_version, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job.job_type, job.source_file, job.records_total, job.records_valid,
             job.records_fixed, job.records_rejected, job.started_at, job.completed_at,
             job.data_version, job.notes),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  AuditLog
# ═══════════════════════════════════════════════════════════

def insert_audit_log(db_path: str, log: AuditLog) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO audit_logs
               (table_name, record_id, field_name, old_value, new_value,
                reason, changed_by, data_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (log.table_name, log.record_id, log.field_name,
             log.old_value, log.new_value, log.reason,
             log.changed_by, log.data_version),
        )
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  Goals
# ═══════════════════════════════════════════════════════════

def bulk_insert_goals(db_path: str, goals: list[dict]) -> int:
    """批量导入进球记录。返回导入条数。"""
    if not goals:
        return 0

    conn = get_connection(db_path)
    try:
        sql = """INSERT OR REPLACE INTO goals
                 (goal_id, match_id, player_id, family_name, given_name,
                  shirt_number, team_id, source_team_id, team_name,
                  minute_label, minute_regulation, minute_stoppage,
                  match_period, own_goal, penalty)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        data = [
            (g.get("goal_id", ""), g.get("match_id", ""),
             g.get("player_id", ""), g.get("family_name", ""), g.get("given_name", ""),
             int(g.get("shirt_number", 0) or 0),
             g.get("team_id", ""), g.get("source_team_id", ""), g.get("team_name", ""),
             g.get("minute_label", ""),
             int(g.get("minute_regulation", 0) or 0),
             int(g.get("minute_stoppage", 0) or 0),
             g.get("match_period", ""),
             int(g.get("own_goal", 0) or 0),
             int(g.get("penalty", 0) or 0))
            for g in goals
        ]
        conn.executemany(sql, data)
        conn.commit()
        return len(data)
    finally:
        conn.close()


def query_goals_by_match(db_path: str, match_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM goals WHERE match_id = ? ORDER BY minute_regulation, minute_stoppage",
            (match_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  查询
# ═══════════════════════════════════════════════════════════

def query_all_matches(db_path: str) -> list[Match]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM matches ORDER BY match_date").fetchall()
        return [_row_to_match(row) for row in rows]
    finally:
        conn.close()


def query_matches_by_team(db_path: str, team_id: str,
                           year: Optional[int] = None,
                           stage: Optional[str] = None) -> list[Match]:
    conn = get_connection(db_path)
    try:
        sql = "SELECT * FROM matches WHERE (home_team_id = ? OR away_team_id = ?)"
        params: list = [team_id, team_id]
        if year:
            sql += " AND tournament_year = ?"
            params.append(year)
        if stage:
            sql += " AND stage = ?"
            params.append(stage)
        sql += " ORDER BY match_date"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_match(row) for row in rows]
    finally:
        conn.close()


def query_head_to_head(db_path: str, team_a: str, team_b: str) -> list[Match]:
    conn = get_connection(db_path)
    try:
        sql = """SELECT * FROM matches
                 WHERE (home_team_id = ? AND away_team_id = ?)
                    OR (home_team_id = ? AND away_team_id = ?)
                 ORDER BY match_date"""
        rows = conn.execute(sql, (team_a, team_b, team_b, team_a)).fetchall()
        return [_row_to_match(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  Document
# ═══════════════════════════════════════════════════════════

def insert_document(db_path: str, doc: dict) -> None:
    """插入文档登记记录。"""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (document_id, title, source_id, file_path, file_type,
                parse_status, chunk_count, parsed_at, data_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc.get("document_id", ""), doc.get("title", ""),
             doc.get("source_id", ""), doc.get("file_path", ""),
             doc.get("file_type", ""), doc.get("parse_status", "pending"),
             doc.get("chunk_count", 0), doc.get("parsed_at", ""),
             doc.get("data_version", "")),
        )
        conn.commit()
    finally:
        conn.close()


def query_documents(db_path: str, parse_status: str = "") -> list[dict]:
    """查询文档登记记录，可按解析状态过滤。"""
    conn = get_connection(db_path)
    try:
        if parse_status:
            rows = conn.execute(
                "SELECT * FROM documents WHERE parse_status = ? ORDER BY document_id",
                (parse_status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY document_id"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  导出
# ═══════════════════════════════════════════════════════════

def export_matches_to_json(db_path: str, output_path: str) -> str:
    matches = query_all_matches(db_path)
    data = [m.to_dict() for m in matches]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path.resolve())


def count_records(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        tables = ["tournaments", "teams", "team_aliases", "matches",
                   "sources", "match_sources", "goals", "import_jobs", "audit_logs"]
        counts = {}
        for table in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                counts[table] = row["cnt"] if row else 0
            except sqlite3.OperationalError:
                counts[table] = "表不存在"
        return counts
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
#  内部工具
# ═══════════════════════════════════════════════════════════

def _row_to_match(row: sqlite3.Row) -> Match:
    return Match(
        match_id=row["match_id"],
        tournament_id=row["tournament_id"] or "",
        tournament_year=row["tournament_year"],
        match_date=row["match_date"],
        raw_match_date=row["raw_match_date"] or "",
        stage=row["stage"],
        stage_name=row["stage_name"] or "",
        group_name=row["group_name"] or "",
        venue=row["venue"] or "",
        city=row["city"] or "",
        home_team_id=row["home_team_id"],
        away_team_id=row["away_team_id"],
        home_score_90=row["home_score_90"],
        away_score_90=row["away_score_90"],
        home_score_et=row["home_score_et"],
        away_score_et=row["away_score_et"],
        home_penalties=row["home_penalties"],
        away_penalties=row["away_penalties"],
        winner_team_id=row["winner_team_id"],
        result_type=row["result_type"],
        score_display=row["score_display"],
        penalty_score=row["penalty_score"] or "",
        data_version=row["data_version"] or "v2",
    )
