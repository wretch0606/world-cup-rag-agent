"""Typed entities used by the World Cup data pipeline.

The module intentionally contains no database or validation side effects. It is
the shared boundary between cleaning, SQLite persistence and fact generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class SerializableEntity:
    """Small dataclass mixin for JSON-ready dictionaries."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Tournament(SerializableEntity):
    tournament_id: str
    year: int
    host: str = ""
    host_en: str = ""
    start_date: str = ""
    end_date: str = ""
    teams_count: int = 32
    champion: str = ""
    top_scorer: str = ""
    top_scorer_goals: int = 0


@dataclass(slots=True)
class Team(SerializableEntity):
    team_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    confederation: str = ""
    fifa_code: str = ""


@dataclass(slots=True)
class TeamAlias(SerializableEntity):
    team_id: str
    alias: str
    normalized_alias: str
    language: str = ""
    alias_type: str = ""
    alias_id: int | None = None


@dataclass(slots=True)
class Match(SerializableEntity):
    match_id: str
    tournament_year: int
    match_date: str
    stage: str
    home_team_id: str
    away_team_id: str
    home_score_90: int
    away_score_90: int
    result_type: str
    score_display: str
    tournament_id: str = ""
    raw_match_date: str = ""
    stage_name: str = ""
    group_name: str = ""
    venue: str = ""
    city: str = ""
    home_score_et: int | None = None
    away_score_et: int | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None
    winner_team_id: str | None = None
    penalty_score: str = ""
    data_version: str = "2026-07-16-v2"


@dataclass(slots=True)
class Source(SerializableEntity):
    source_id: str
    title: str = ""
    source_url: str = ""
    source_type: str = ""
    publisher: str = ""
    retrieved_at: str = ""
    checksum: str = ""
    license_info: str = ""
    data_version: str = ""
    description: str = ""


@dataclass(slots=True)
class MatchSource(SerializableEntity):
    match_id: str
    source_id: str
    evidence_type: str = ""
    is_primary: int = 0
    notes: str = ""


@dataclass(slots=True)
class Goal(SerializableEntity):
    goal_id: str
    match_id: str
    player_id: str = ""
    family_name: str = ""
    given_name: str = ""
    shirt_number: int = 0
    team_id: str = ""
    source_team_id: str = ""
    team_name: str = ""
    minute_label: str = ""
    minute_regulation: int = 0
    minute_stoppage: int = 0
    match_period: str = ""
    own_goal: int = 0
    penalty: int = 0


@dataclass(slots=True)
class StructuredFact(SerializableEntity):
    match_id: str
    document_id: str
    tournament_year: int
    match_date: str
    stage: str
    stage_name: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    home_score_90: int
    away_score_90: int
    score_display: str
    result_type: str
    fact_text: str
    home_score_et: int | None = None
    away_score_et: int | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None
    penalty_score: str = ""
    winner_team_id: str | None = None
    source_ids: list[str] = field(default_factory=list)
    data_version: str = ""
    checksum: str = ""


@dataclass(slots=True)
class ImportJob(SerializableEntity):
    job_type: str = ""
    source_file: str = ""
    records_total: int = 0
    records_valid: int = 0
    records_fixed: int = 0
    records_rejected: int = 0
    started_at: str = ""
    completed_at: str = ""
    data_version: str = ""
    notes: str = ""
    job_id: int | None = None


@dataclass(slots=True)
class AuditLog(SerializableEntity):
    table_name: str
    record_id: str
    field_name: str
    old_value: str = ""
    new_value: str = ""
    reason: str = ""
    changed_by: str = "C"
    changed_at: str = ""
    data_version: str = "v2"
    audit_id: int | None = None


@dataclass(slots=True)
class CleaningReport(SerializableEntity):
    total_records: int = 0
    valid: int = 0
    fixed: int = 0
    rejected: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_warning(self, match_id: str, field: str, value: str, action: str) -> None:
        self.warnings.append(
            {
                "match_id": match_id,
                "field": field,
                "value": value,
                "action": action,
            }
        )
        self.fixed += 1

    def add_error(
        self,
        match_id: str,
        message: str,
        *,
        field: str = "",
        value: str = "",
    ) -> None:
        error = {"match_id": match_id, "message": message}
        if field:
            error["field"] = field
        if value:
            error["value"] = value
        self.errors.append(error)
        self.rejected += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_records": self.total_records,
                "valid": self.valid,
                "fixed": self.fixed,
                "rejected": self.rejected,
            },
            "warnings": self.warnings,
            "errors": self.errors,
        }
