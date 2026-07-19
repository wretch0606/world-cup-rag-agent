-- ============================================================
-- 世界杯知识库 — SQLite 建表脚本 v2
-- 与 RAG 接口契约 rag-v1.0-draft 对齐
-- 阶段枚举使用英文，中文显示名通过 stage_name 或映射表提供
-- ============================================================

-- ── 届次表 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id  TEXT PRIMARY KEY,         -- "WC-2022"
    year           INTEGER NOT NULL UNIQUE,  -- 2022
    host           TEXT NOT NULL,            -- "卡塔尔"
    host_en        TEXT DEFAULT '',          -- "Qatar"
    start_date     TEXT NOT NULL,            -- "2022-11-20"
    end_date       TEXT NOT NULL,            -- "2022-12-18"
    teams_count    INTEGER DEFAULT 32,
    champion       TEXT DEFAULT '',          -- "team_ARG"
    top_scorer     TEXT DEFAULT '',
    top_scorer_goals INTEGER DEFAULT 0
);

-- ── 球队表 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teams (
    team_id        TEXT PRIMARY KEY,         -- "team_ARG"
    canonical_name TEXT NOT NULL,            -- "阿根廷"
    aliases_json   TEXT DEFAULT '[]',        -- JSON 数组 ["Argentina", "ARG"]
    confederation  TEXT DEFAULT '',          -- "CONMEBOL"
    fifa_code      TEXT DEFAULT ''           -- "ARG"
);

-- ── 球队别名表（独立表，支持索引查询）────────────────
CREATE TABLE IF NOT EXISTS team_aliases (
    alias_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         TEXT NOT NULL REFERENCES teams(team_id),
    alias           TEXT NOT NULL,           -- 别名字符串
    language        TEXT DEFAULT '',         -- "zh" / "en" / "fifa"
    alias_type      TEXT DEFAULT '',         -- "full_name" / "short_name" / "historical" / "fifa_code"
    normalized_alias TEXT NOT NULL,          -- 小写去空格，用于匹配
    UNIQUE(team_id, normalized_alias)
);
CREATE INDEX IF NOT EXISTS idx_team_aliases_normalized ON team_aliases(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_team_aliases_team ON team_aliases(team_id);

-- ── 比赛表（核心）───────────────────────────────────────
CREATE TABLE IF NOT EXISTS matches (
    match_id         TEXT PRIMARY KEY,               -- "M-2022-64"
    tournament_id    TEXT DEFAULT '' REFERENCES tournaments(tournament_id),  -- "WC-2022"
    tournament_year  INTEGER NOT NULL,               -- 2022
    match_date       TEXT NOT NULL,                  -- "2022-12-18"
    raw_match_date   TEXT DEFAULT '',                 -- 保留原始日期文本（可追溯）
    stage            TEXT NOT NULL,                  -- "final" (英文 enum)
    stage_name       TEXT DEFAULT '',                 -- "决赛" (中文显示名)
    group_name       TEXT DEFAULT '',                -- "A组"
    venue            TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    -- 参赛双方
    home_team_id     TEXT NOT NULL REFERENCES teams(team_id),
    away_team_id     TEXT NOT NULL REFERENCES teams(team_id),
    -- 90 分钟常规时间比分
    home_score_90    INTEGER NOT NULL,
    away_score_90    INTEGER NOT NULL,
    -- 加时累计比分（无加时则为 NULL）
    home_score_et    INTEGER,
    away_score_et    INTEGER,
    -- 点球大战比分（无点球则为 NULL）
    home_penalties   INTEGER,
    away_penalties   INTEGER,
    -- 结果
    winner_team_id   TEXT REFERENCES teams(team_id),  -- 平局时为 NULL
    result_type      TEXT NOT NULL                   -- "regulation" / "extra_time" / "penalties" / "draw"
                     CHECK(result_type IN ('regulation','extra_time','penalties','draw')),
    score_display    TEXT NOT NULL,                  -- "3:3" (正式比分，不含点球)
    penalty_score    TEXT DEFAULT '',                 -- "4:2" (点球比分单独字段)
    -- 来源和版本
    data_version     TEXT DEFAULT 'v2',
    -- 约束：主队不能等于客队
    CHECK(home_team_id != away_team_id),
    -- 约束：分数不得为负
    CHECK(home_score_90 >= 0 AND away_score_90 >= 0),
    CHECK(home_score_et IS NULL OR home_score_et >= 0),
    CHECK(away_score_et IS NULL OR away_score_et >= 0),
    CHECK(home_penalties IS NULL OR home_penalties >= 0),
    CHECK(away_penalties IS NULL OR away_penalties >= 0)
);

-- ── 来源表 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    source_id    TEXT PRIMARY KEY,           -- "source-kaggle-001"
    title        TEXT DEFAULT '',            -- "FIFA World Cup 1930-2022..."
    source_url   TEXT DEFAULT '',            -- 公开可访问 URL，禁止本地路径
    source_type  TEXT DEFAULT '',            -- csv / json / pdf / web
    publisher    TEXT DEFAULT '',            -- 出版/提供方
    retrieved_at TEXT DEFAULT '',            -- "2026-07-16"
    checksum     TEXT DEFAULT '',            -- 文件内容校验值
    license_info TEXT DEFAULT '',            -- 许可说明
    data_version TEXT DEFAULT '',            -- 原始数据版本
    description  TEXT DEFAULT ''             -- 来源内容描述
);

-- ── 比赛—来源 多对多关联表 ────────────────────────────
CREATE TABLE IF NOT EXISTS match_sources (
    match_id       TEXT NOT NULL REFERENCES matches(match_id),
    source_id      TEXT NOT NULL REFERENCES sources(source_id),
    evidence_type  TEXT DEFAULT '',          -- "primary" / "cross_check" / "supplementary"
    is_primary     INTEGER DEFAULT 0,        -- 1 = 主要来源
    notes          TEXT DEFAULT '',
    PRIMARY KEY (match_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_match_sources_match ON match_sources(match_id);
CREATE INDEX IF NOT EXISTS idx_match_sources_source ON match_sources(source_id);

-- ── 进球表 ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    goal_id           TEXT PRIMARY KEY,               -- "G-00001"
    match_id          TEXT NOT NULL REFERENCES matches(match_id),
    player_id         TEXT DEFAULT '',                -- "P-08962"
    family_name       TEXT DEFAULT '',                -- "Mbappé"
    given_name        TEXT DEFAULT '',                -- "Kylian"
    shirt_number      INTEGER DEFAULT 0,
    team_id           TEXT DEFAULT '' REFERENCES teams(team_id),  -- "team_FRA" (外键)
    source_team_id    TEXT DEFAULT '',                 -- 旧格式 ID 保留在此（如 "T-28"）
    team_name         TEXT DEFAULT '',                -- "France"
    minute_label      TEXT DEFAULT '',                -- "80'"
    minute_regulation INTEGER DEFAULT 0,              -- 80
    minute_stoppage   INTEGER DEFAULT 0,              -- 伤停补时分钟
    match_period      TEXT DEFAULT '',                -- "first half" / "second half" / "extra time" / "penalties"
    own_goal          INTEGER DEFAULT 0,              -- 0=正常进球, 1=乌龙
    penalty           INTEGER DEFAULT 0               -- 0=运动战, 1=点球
);
CREATE INDEX IF NOT EXISTS idx_goals_match  ON goals(match_id);
CREATE INDEX IF NOT EXISTS idx_goals_player ON goals(player_id);
CREATE INDEX IF NOT EXISTS idx_goals_team   ON goals(team_id);
CREATE INDEX IF NOT EXISTS idx_goals_period ON goals(match_period);

-- ── 导入任务记录 ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS import_jobs (
    job_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type       TEXT DEFAULT '',          -- "full_import" / "incremental" / "fix"
    source_file    TEXT DEFAULT '',
    records_total  INTEGER DEFAULT 0,
    records_valid  INTEGER DEFAULT 0,
    records_fixed  INTEGER DEFAULT 0,
    records_rejected INTEGER DEFAULT 0,
    started_at     TEXT DEFAULT '',
    completed_at   TEXT DEFAULT '',
    data_version   TEXT DEFAULT '',
    notes          TEXT DEFAULT ''
);

-- ── 数据修正审计日志 ────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    field_name  TEXT NOT NULL,
    old_value   TEXT DEFAULT '',
    new_value   TEXT DEFAULT '',
    reason      TEXT DEFAULT '',
    changed_by  TEXT DEFAULT 'C',
    changed_at  TEXT DEFAULT (datetime('now')),
    data_version TEXT DEFAULT 'v2'
);
CREATE INDEX IF NOT EXISTS idx_audit_table_record ON audit_logs(table_name, record_id);

-- ── 文档登记表（PDF、网页等）───────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    document_id   TEXT PRIMARY KEY,          -- "document-001"
    title         TEXT DEFAULT '',
    source_id     TEXT REFERENCES sources(source_id),
    file_path     TEXT DEFAULT '',            -- 非本地路径，可追溯的存档位置
    file_type     TEXT DEFAULT '',            -- "pdf" / "html" / "txt"
    parse_status  TEXT DEFAULT 'pending',     -- "pending" / "parsed" / "failed"
    chunk_count   INTEGER DEFAULT 0,
    parsed_at     TEXT DEFAULT '',
    data_version  TEXT DEFAULT ''
);

-- ============================================================
--  索引 ──高频查询优化
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_matches_year      ON matches(tournament_year);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id);
CREATE INDEX IF NOT EXISTS idx_matches_stage     ON matches(stage);
CREATE INDEX IF NOT EXISTS idx_matches_home      ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away      ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_result    ON matches(result_type);
CREATE INDEX IF NOT EXISTS idx_matches_date      ON matches(match_date);

-- 复合索引：按球队 + 年份查询（高频）
CREATE INDEX IF NOT EXISTS idx_matches_home_year ON matches(home_team_id, tournament_year);
CREATE INDEX IF NOT EXISTS idx_matches_away_year ON matches(away_team_id, tournament_year);

-- 唯一约束：比赛签名不重复
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_signature
    ON matches(tournament_year, match_date, home_team_id, away_team_id, stage);
