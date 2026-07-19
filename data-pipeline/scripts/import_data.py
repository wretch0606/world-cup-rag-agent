"""
一键导入脚本 (v1 - 已弃用)

⚠️ 此脚本已弃用，请使用 import_data_v2.py。
   v2 支持：22届 tournament 数据、英文阶段枚举、tournament 日期范围校验、
   penalty_score 独立字段、source_ids 数组、match_sources 关联表。

用法（遗留兼容）:
    python scripts/import_data.py --input raw_data/matches_2018.csv --source_type csv --year 2018

流程：
1. 读取原始数据文件
2. 逐条清洗
3. 写入 SQLite
4. 生成事实文本
5. 输出清洗报告
"""

import sys
import json
import argparse
from pathlib import Path

# 将 backend 加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.data_importer import import_csv, import_json, compute_checksum, generate_source_id
from services.data_cleaner import load_team_aliases, clean_match_record
from services.db_schema import (
    create_tables, get_connection,
    insert_tournament, insert_source, bulk_insert_matches,
    import_teams_from_aliases, count_records,
    query_all_matches, query_all_teams,
)
from services.fact_generator import generate_all_match_facts, generate_tournament_summary
from models.entities import Tournament, Match, Source
from models.entities import CleaningReport


def main():
    parser = argparse.ArgumentParser(description="世界杯赛事数据一键导入")
    parser.add_argument("--input", "-i", required=True, help="原始数据文件路径")
    parser.add_argument("--source_type", "-t", required=True,
                        choices=["csv", "json"], help="数据格式")
    parser.add_argument("--year", "-y", type=int, required=True, help="世界杯年份")
    parser.add_argument("--host", default="", help="主办国")
    parser.add_argument("--db", default="data/worldcup.db", help="SQLite 数据库路径")
    parser.add_argument("--schema", default="data/schema.sql", help="建表 SQL 路径")
    parser.add_argument("--aliases", default="data/team_aliases.json",
                        help="球队别名文件路径")
    parser.add_argument("--output-facts", default="data/match_facts.json",
                        help="事实文本输出路径")
    parser.add_argument("--output-report", default="data/cleaning_report.json",
                        help="清洗报告输出路径")
    parser.add_argument("--goals", default="", help="进球数据 CSV 文件路径（可选）")
    args = parser.parse_args()

    # ── 0. 初始化 ──
    db_path = args.db
    schema_path = args.schema
    alias_path = args.aliases

    # 确保数据库目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 建表
    print(f"[1/6] 建表...")
    create_tables(db_path, schema_path)

    # 导入球队
    print(f"[2/6] 导入球队...")
    team_count = import_teams_from_aliases(db_path, alias_path)
    print(f"  已导入 {team_count} 支球队")

    # ── 1. 读取原始数据 ──
    print(f"[3/6] 读取原始数据: {args.input}")
    if args.source_type == "csv":
        # 自动检测是否为 Kaggle 数据集（通过检查第一行列名）
        field_map = _detect_field_map(args.input)
        if field_map:
            print(f"  检测到 Kaggle 数据集，启用字段映射")
        raw_records = import_csv(args.input, field_map=field_map)
        # Kaggle 数据预处理：Datetime → match_date, Win conditions → 加时/点球
        raw_records = _preprocess_kaggle(raw_records)
    else:
        raw_records = import_json(args.input)
    print(f"  原始记录数: {len(raw_records)}")

    # ── 2. 注册来源 ──
    print(f"[4/6] 注册数据来源...")
    checksum = compute_checksum(args.input)
    source_id = generate_source_id(args.source_type, Path(args.input).stem)
    source = Source(
        source_id=source_id,
        title=Path(args.input).name,
        source_url=args.input,
        source_type=args.source_type,
        checksum=checksum,
    )
    insert_source(db_path, source)

    # 注册赛事届次
    if args.host:
        tournament = Tournament(
            tournament_id=f"WC{args.year}",
            year=args.year,
            host=args.host,
            start_date=f"{args.year}-06-01",
            end_date=f"{args.year}-07-15",
        )
        insert_tournament(db_path, tournament)

    # ── 3. 清洗 ──
    print(f"[5/6] 清洗数据...")
    alias_data = load_team_aliases(alias_path)
    cleaned_matches = []
    total_report = CleaningReport(total_records=len(raw_records))

    for i, record in enumerate(raw_records):
        cleaned, report = clean_match_record(record, alias_data, source_ids=[source_id])
        if cleaned:
            cleaned_matches.append(cleaned)
        total_report.valid += report.valid
        total_report.fixed += report.fixed
        total_report.rejected += report.rejected
        total_report.warnings.extend(report.warnings)
        total_report.errors.extend(report.errors)

    # 写入数据库
    if cleaned_matches:
        match_objects = [_dict_to_match(m) for m in cleaned_matches]
        inserted = bulk_insert_matches(db_path, match_objects)
        print(f"  有效: {inserted}, 修复: {total_report.fixed}, 拒绝: {total_report.rejected}")

    # 保存清洗报告
    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(total_report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  清洗报告已保存: {report_path}")

    # ── 4. 生成事实文本 ──
    print(f"[6/7] 生成事实文本...")
    all_matches = query_all_matches(db_path)
    all_teams = {t.team_id: t for t in query_all_teams(db_path)}
    facts = generate_all_match_facts(all_matches, all_teams, args.host)

    facts_path = Path(args.output_facts)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(
        json.dumps(facts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  事实文本已保存: {facts_path} ({len(facts)} 条)")

    # ── 5. 导入进球数据（可选）──
    if args.goals:
        _import_goals(args.goals, db_path)

    # ── 统计 ──
    print("\n===== 导入完成 =====")
    counts = count_records(db_path)
    for table, count in counts.items():
        print(f"  {table}: {count} 条")
    print(f"\n数据文件: {db_path}")
    print(f"事实文本: {facts_path}")
    print(f"清洗报告: {report_path}")


def _dict_to_match(d: dict) -> Match:
    """将清洗后的 dict 转为 Match dataclass。"""
    return Match(
        match_id=d.get("match_id", ""),
        tournament_id=d.get("tournament_id", ""),
        tournament_year=d.get("tournament_year", 0),
        match_date=d.get("match_date", ""),
        raw_match_date=d.get("raw_match_date", ""),
        stage=d.get("stage", ""),
        stage_name=d.get("stage_name", ""),
        group_name=d.get("group_name", ""),
        venue=d.get("venue", ""),
        home_team_id=d.get("home_team_id", ""),
        away_team_id=d.get("away_team_id", ""),
        home_score_90=d.get("home_score_90", 0),
        away_score_90=d.get("away_score_90", 0),
        home_score_et=d.get("home_score_et"),
        away_score_et=d.get("away_score_et"),
        home_penalties=d.get("home_penalties"),
        away_penalties=d.get("away_penalties"),
        winner_team_id=d.get("winner_team_id"),
        result_type=d.get("result_type", ""),
        score_display=d.get("score_display", ""),
        penalty_score=d.get("penalty_score", ""),
        data_version=d.get("data_version", "2026-07-16-v2"),
    )


# ── 进球数据导入 ──────────────────────────────────────────

def _import_goals(file_path: str, db_path: str) -> None:
    """导入进球 CSV 到 goals 表。"""
    import csv
    from services.db_schema import bulk_insert_goals

    print(f"\n[7/7] 导入进球数据: {Path(file_path).name}")
    records = []
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin-1"]:
        try:
            with open(file_path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("goal_id", "").strip():
                        records.append(row)
                break
        except UnicodeError:
            continue

    if not records:
        print("  无进球记录")
        return

    count = bulk_insert_goals(db_path, records)
    print(f"  已导入 {count} 条进球记录")

    # 统计
    from services.db_schema import get_connection
    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM goals").fetchone()["n"]
        matches_with_goals = conn.execute(
            "SELECT COUNT(DISTINCT match_id) as n FROM goals"
        ).fetchone()["n"]
        penalties = conn.execute(
            "SELECT COUNT(*) as n FROM goals WHERE penalty = 1"
        ).fetchone()["n"]
        own = conn.execute(
            "SELECT COUNT(*) as n FROM goals WHERE own_goal = 1"
        ).fetchone()["n"]
    finally:
        conn.close()

    print(f"  覆盖比赛: {matches_with_goals} 场")
    print(f"  其中点球: {penalties} 个, 乌龙: {own} 个")


# ── Kaggle 数据集适配 ──────────────────────────────────────

def _detect_field_map(file_path: str) -> dict | None:
    """
    检测 CSV 是否为 Kaggle 格式（通过检查列头）。
    如果是，返回字段映射表；否则返回 None。
    """
    import csv

    # 尝试多种编码读取第一行
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin-1"]:
        try:
            with open(file_path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        return None

    # Kaggle 数据集特征：同时存在 "Home Team Name" 和 "Match Date"
    has_home = "Home Team Name" in headers
    has_date = "Match Date" in headers
    if has_home and has_date:
        from services.data_importer import KAGGLE_MATCH_MAP
        return KAGGLE_MATCH_MAP
    return None


def _preprocess_kaggle(records: list[dict]) -> list[dict]:
    """
    预处理 Kaggle 数据集：
    - match_date "7/13/1930" 保留原值（normalize_date 会处理格式转换）
    - home_score_90/away_score_90 字符串 → int
    - home_penalties/away_penalties → 非点球大战清为 None
    - 保留 Penalty Shootout 标记给 result_type 判断
    """
    processed = []
    for rec in records:
        r = dict(rec)

        # ── 比分转为 int ──
        for key in ("home_score_90", "away_score_90"):
            val = str(r.get(key, "0")).strip()
            try:    r[key] = int(val)
            except: r[key] = 0

        # ── 点球分数字段：只有实际打了点球才保留 ──
        is_shootout = str(r.get("penalty_shootout_flag", "0")).strip() == "1"
        for key in ("home_penalties", "away_penalties"):
            val = str(r.get(key, "0")).strip()
            if is_shootout:
                try:    r[key] = int(val)
                except: r[key] = None
            else:
                r[key] = None  # 非点球大战 → 清空

        # ── 清理不需要的原始列 ──
        # 保留 extra_time_flag 和原始 match_id，供清洗阶段使用
        keep = {"home_team", "away_team", "match_date",
                "home_score_90", "away_score_90", "home_penalties", "away_penalties",
                "stage", "group_name", "venue", "match_id", "tournament_year",
                "extra_time_flag"}
        for key in list(r.keys()):
            if key not in keep:
                r.pop(key)

        processed.append(r)
    return processed


if __name__ == "__main__":
    main()
