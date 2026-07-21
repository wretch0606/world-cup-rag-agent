"""SQLiteFrontendDataProvider — read-only SQLite adapter for live match data.

Uses read-only connections, parameterised queries, and the shared mapper.
Never imports Chroma, models, or modifies the database.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.repositories.mapper import build_match_summary
from backend.schemas.common import (
    DocumentFilters,
    MatchFilters,
    PaginatedMatches,
    RelationFilters,
    StageEnum,
)

logger = logging.getLogger("backend.sqlite")


class SQLiteFrontendProviderError(RuntimeError):
    """Raised when the SQLite provider cannot be initialised."""


class SQLiteFrontendDataProvider:
    """Read-only SQLite data provider."""

    def __init__(self, db_path: str) -> None:
        if not db_path or not Path(db_path).exists():
            raise SQLiteFrontendProviderError(
                f"Database not found at '{db_path}'. "
                "Set WORLD_CUP_DB_PATH to a valid worldcup_v2.db path, "
                "or switch FRONTEND_DATA_MODE=mock."
            )
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------
    def _connect(self, *, readonly: bool = True) -> sqlite3.Connection:
        """Open a read-only connection using URI mode."""
        if readonly:
            uri = f"file:{self._db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=1")
        return conn

    # ------------------------------------------------------------------
    # FrontendDataProvider implementation
    # ------------------------------------------------------------------
    def get_filter_options(self) -> dict:
        conn = self._connect()
        try:
            # Tournaments — "label" is generated, not a DB column
            tournaments = [
                {"year": r["year"], "label": f"{r['year']} {r['host']}世界杯", "host": r["host"]}
                for r in conn.execute(
                    "SELECT year, host FROM tournaments ORDER BY year DESC"
                ).fetchall()
            ]
            # Teams
            teams = [
                {"team_id": r["team_id"], "name": r["canonical_name"]}
                for r in conn.execute(
                    "SELECT team_id, canonical_name FROM teams ORDER BY canonical_name"
                ).fetchall()
            ]
            # Stages (static contract order)
            stages = [{"value": s.value, "label": s.label, "order": s.order} for s in StageEnum]
            # Result types
            result_types = [
                {"value": "regulation", "label": "常规时间决胜"},
                {"value": "extra_time", "label": "加时赛决胜"},
                {"value": "penalties", "label": "点球大战决胜"},
                {"value": "draw", "label": "平局"},
            ]
            return {
                "data_status": "live",
                "tournaments": tournaments,
                "teams": teams,
                "stages": stages,
                "result_types": result_types,
            }
        finally:
            conn.close()

    def list_matches(
        self, filters: MatchFilters, page: int = 1, page_size: int = 20
    ) -> PaginatedMatches:
        conn = self._connect()
        try:
            where: list[str] = []
            params: list = []

            if filters.years:
                where.append(f"m.tournament_year IN ({','.join('?' * len(filters.years))})")
                params.extend(filters.years)
            if filters.team_ids:
                placeholders = ",".join("?" * len(filters.team_ids))
                where.append(
                    f"(m.home_team_id IN ({placeholders}) OR m.away_team_id IN ({placeholders}))"
                )
                params.extend(filters.team_ids)
                params.extend(filters.team_ids)
            if filters.stages:
                stage_values = [s.value if hasattr(s, "value") else s for s in filters.stages]
                where.append(f"m.stage IN ({','.join('?' * len(stage_values))})")
                params.extend(stage_values)
            if filters.result_types:
                rt_values = [r.value if hasattr(r, "value") else r for r in filters.result_types]
                where.append(f"m.result_type IN ({','.join('?' * len(rt_values))})")
                params.extend(rt_values)
            if filters.has_penalties is True:
                where.append("m.result_type = 'penalties'")

            where_clause = " AND ".join(where) if where else "1=1"

            # Count
            count_sql = f"SELECT COUNT(*) FROM matches m WHERE {where_clause}"
            total = conn.execute(count_sql, params).fetchone()[0]

            # Fetch page
            offset = (page - 1) * page_size
            query = f"""
                SELECT m.*,
                       ht.canonical_name AS home_team_name,
                       at.canonical_name AS away_team_name,
                       wt.canonical_name AS winner_team_name
                FROM matches m
                LEFT JOIN teams ht ON m.home_team_id = ht.team_id
                LEFT JOIN teams at ON m.away_team_id = at.team_id
                LEFT JOIN teams wt ON m.winner_team_id = wt.team_id
                WHERE {where_clause}
                ORDER BY m.tournament_year DESC, m.match_date ASC, m.match_id ASC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query, params + [page_size, offset]).fetchall()

            items = [build_match_summary(dict(r)) for r in rows]

            af: dict = {
                "years": filters.years,
                "team_ids": filters.team_ids,
                "stages": [s.value if hasattr(s, "value") else s for s in filters.stages],
                "result_types": [
                    r.value if hasattr(r, "value") else r for r in filters.result_types
                ],
                "has_penalties": filters.has_penalties,
            }
            return PaginatedMatches(
                items=items, total=total, page=page, page_size=page_size, applied_filters=af
            )
        finally:
            conn.close()

    def get_match(self, match_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT m.*,
                          ht.canonical_name AS home_team_name,
                          at.canonical_name AS away_team_name,
                          wt.canonical_name AS winner_team_name
                   FROM matches m
                   LEFT JOIN teams ht ON m.home_team_id = ht.team_id
                   LEFT JOIN teams at ON m.away_team_id = at.team_id
                   LEFT JOIN teams wt ON m.winner_team_id = wt.team_id
                   WHERE m.match_id = ?""",
                (match_id,),
            ).fetchone()
            if row is None:
                return None

            data = build_match_summary(dict(row))
            data["data_status"] = "live"

            # Venue / city
            data["venue"] = row["venue"] or None
            data["city"] = None  # Not in current schema; kept for contract compliance

            # Timeline — basic structure, detailed event data pending goals table integration
            data["timeline"] = {
                "regular_time": [],
                "extra_time": [],
                "shootout": {
                    "available": False,
                    "home_score": data["score"].get("penalties", {}).get("home", 0)
                    if data["score"].get("penalties")
                    else 0,
                    "away_score": data["score"].get("penalties", {}).get("away", 0)
                    if data["score"].get("penalties")
                    else 0,
                    "events": [],
                    "message": "逐轮点球数据暂不可用"
                    if data["score"].get("penalties")
                    else "本场比赛未进行点球大战",
                },
            }

            # Sources
            src_rows = conn.execute(
                """SELECT s.* FROM sources s
                   INNER JOIN match_sources ms ON s.source_id = ms.source_id
                   WHERE ms.match_id = ?""",
                (match_id,),
            ).fetchall()
            data["sources"] = [
                {
                    "source_id": s["source_id"],
                    "title": s["title"],
                    "url": s["source_url"] if s["source_url"] else None,
                    "page": None,
                    "document_id": None,
                    "data_version": (s["data_version"] if s["data_version"] else None),
                    "used_for_fact_ids": [],
                }
                for s in src_rows
            ]
            return data
        finally:
            conn.close()

    def get_team_relations(
        self, team_id: str, filters: RelationFilters, page: int = 1, page_size: int = 20
    ) -> dict:
        conn = self._connect()
        try:
            team_row = conn.execute(
                "SELECT team_id, canonical_name FROM teams WHERE team_id = ?", (team_id,)
            ).fetchone()
            if team_row is None:
                return {
                    "data_status": "live",
                    "team": None,
                    "stats": {},
                    "matches": [],
                    "graph": {"scope": "team_relations", "nodes": [], "edges": []},
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "applied_filters": {},
                }

            where: list[str] = ["(m.home_team_id = ? OR m.away_team_id = ?)"]
            params: list = [team_id, team_id]

            if filters.year_from:
                where.append("m.tournament_year >= ?")
                params.append(filters.year_from)
            if filters.year_to:
                where.append("m.tournament_year <= ?")
                params.append(filters.year_to)
            if filters.opponent_id:
                where.append("(m.home_team_id = ? OR m.away_team_id = ?)")
                params.extend([filters.opponent_id, filters.opponent_id])
            if filters.stages:
                sv = [s.value if hasattr(s, "value") else s for s in filters.stages]
                where.append(f"m.stage IN ({','.join('?' * len(sv))})")
                params.extend(sv)
            if filters.has_penalties is True:
                where.append("m.result_type = 'penalties'")

            where_clause = " AND ".join(where)

            rows = conn.execute(
                f"""SELECT m.*,
                          ht.canonical_name AS home_team_name,
                          at.canonical_name AS away_team_name,
                          wt.canonical_name AS winner_team_name
                   FROM matches m
                   LEFT JOIN teams ht ON m.home_team_id = ht.team_id
                   LEFT JOIN teams at ON m.away_team_id = at.team_id
                   LEFT JOIN teams wt ON m.winner_team_id = wt.team_id
                   WHERE {where_clause}
                   ORDER BY m.tournament_year DESC, m.match_date ASC
                   LIMIT ? OFFSET ?""",
                params + [page_size, (page - 1) * page_size],
            ).fetchall()

            matches = [build_match_summary(dict(r)) for r in rows]

            # Stats
            all_rows = conn.execute(
                f"SELECT m.result_type, m.winner_team_id FROM matches m WHERE {where_clause}",
                params,
            ).fetchall()
            stats = {
                "matches": len(all_rows),
                "regulation_or_extra_time_wins": 0,
                "draws": 0,
                "penalty_advances": 0,
                "losses": 0,
            }
            nodes_set: dict[str, dict] = {}
            for r in all_rows:
                w = r["winner_team_id"]
                if w == team_id:
                    if r["result_type"] == "penalties":
                        stats["penalty_advances"] += 1
                    else:
                        stats["regulation_or_extra_time_wins"] += 1
                elif w and w != team_id:
                    stats["losses"] += 1
                else:
                    stats["draws"] += 1

            # Graph
            edges: list[dict] = []
            for m in matches:
                hid, aid = m["home_team"]["team_id"], m["away_team"]["team_id"]
                nodes_set[hid] = {"id": hid, "name": m["home_team"]["name"], "type": "team"}
                nodes_set[aid] = {"id": aid, "name": m["away_team"]["name"], "type": "team"}
                w = m.get("winner_team")
                score_display = m.get("score", {}).get("display", "")
                edges.append(
                    {
                        "id": f"edge-{m['match_id']}",
                        "source": w["team_id"] if (w and w.get("team_id")) else hid,
                        "target": aid
                        if (w and w.get("team_id") and w["team_id"] == hid)
                        else (hid if (w and w.get("team_id") and w["team_id"] != hid) else aid),
                        "type": "match_result",
                        "match_id": m["match_id"],
                        "tournament_year": m["tournament_year"],
                        "stage": m["stage"],
                        "stage_name": m["stage_name"],
                        "result_type": m["result_type"],
                        "winner_team_id": w["team_id"] if w else None,
                        "label": f"{m['tournament_year']} {m['stage_name']} {score_display}",
                    }
                )

            return {
                "data_status": "live",
                "team": {"team_id": team_row["team_id"], "name": team_row["canonical_name"]},
                "stats": stats,
                "matches": matches,
                "graph": {
                    "scope": "team_relations",
                    "nodes": list(nodes_set.values()),
                    "edges": edges,
                },
                "total": len(all_rows),
                "page": page,
                "page_size": page_size,
                "applied_filters": {},
            }
        finally:
            conn.close()

    def list_documents(self, filters: DocumentFilters, page: int = 1, page_size: int = 20) -> dict:
        conn = self._connect()
        try:
            where: list[str] = ["1=1"]
            params: list = []
            if filters.status:
                where.append("d.parse_status = ?")
                params.append(filters.status)
            if filters.data_version:
                where.append("d.data_version = ?")
                params.append(filters.data_version)
            where_clause = " AND ".join(where)

            total = conn.execute(
                f"SELECT COUNT(*) FROM documents d WHERE {where_clause}", params
            ).fetchone()[0]

            rows = conn.execute(
                f"""SELECT d.* FROM documents d
                    WHERE {where_clause}
                    ORDER BY d.parsed_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, (page - 1) * page_size],
            ).fetchall()

            items = [
                {
                    "document_id": r["document_id"],
                    "title": r["title"],
                    "source_id": r["source_id"] or "",
                    "file_type": r["file_type"] or "",
                    "parse_status": r["parse_status"] or "",
                    "chunk_count": r["chunk_count"] or 0,
                    "parsed_at": r["parsed_at"],
                    "data_version": r["data_version"] or "",
                }
                for r in rows
            ]
            return {
                "data_status": "live",
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "applied_filters": {"status": filters.status, "data_version": filters.data_version},
            }
        finally:
            conn.close()
