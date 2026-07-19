"""
一键导入脚本 v2

改进点（对齐整改清单 P0）：
- 加载 22 届 tournament 数据
- 阶段归一为英文 enum + 中文显示名分离
- 日期解析使用 tournament 范围校验
- 保留 raw_match_date 原始值
- penalty_score 独立字段
- 生成 match_facts.jsonl（对齐 RAG 契约）
- 记录 import_jobs
- 批量导入 goals（含 team_id 映射）

用法:
    python scripts/import_data_v2.py --input raw_data/WorldCupMatches.csv --year 1930
    python scripts/import_data_v2.py --input raw_data/WorldCupMatches.csv --year all
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.data_importer import import_csv, import_json, compute_checksum, generate_source_id
from services.data_cleaner import (
    load_team_aliases, clean_match_record,
    load_tournament_data, get_tournament_by_year,
    reset_match_counter,
)
from services.db_schema import (
    create_tables, get_connection,
    insert_tournament, insert_source, bulk_insert_matches, insert_match_source,
    import_teams_from_aliases, import_team_aliases,
    import_tournaments_from_json, import_sources_from_manifest,
    count_records, query_all_matches, query_all_teams,
)
from services.fact_generator import (
    generate_all_match_facts, write_match_facts_jsonl, write_match_facts_json,
)
from models.entities import Tournament, Match, Source, MatchSource, ImportJob
from models.entities import CleaningReport

# 默认路径
BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB = str(BASE_DIR / "data" / "worldcup_v2.db")
DEFAULT_SCHEMA = str(BASE_DIR / "data" / "schema.sql")
DEFAULT_ALIASES = str(BASE_DIR / "data" / "team_aliases.json")
DEFAULT_TOURNAMENTS = str(BASE_DIR / "data" / "tournaments.json")
DEFAULT_SOURCE_MANIFEST = str(BASE_DIR / "data" / "source_manifest.json")


def main():
    parser = argparse.ArgumentParser(description="世界杯赛事数据一键导入 v2")
    parser.add_argument("--input", "-i", required=True, help="原始数据文件路径")
    parser.add_argument("--source_type", "-t", default="csv",
                        choices=["csv", "json"], help="数据格式")
    parser.add_argument("--year", "-y", default="all",
                        help="世界杯年份 (如 2022) 或 'all' (导入全部)")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite 数据库路径")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="建表 SQL 路径")
    parser.add_argument("--aliases", default=DEFAULT_ALIASES, help="球队别名文件")
    parser.add_argument("--output-facts", default=str(BASE_DIR / "data" / "match_facts.jsonl"),
                        help="事实文本 JSONL 输出路径")
    parser.add_argument("--output-facts-json", default=str(BASE_DIR / "data" / "match_facts.json"),
                        help="事实文本 JSON 输出路径")
    parser.add_argument("--output-report", default=str(BASE_DIR / "data" / "cleaning_report.json"),
                        help="清洗报告输出路径")
    args = parser.parse_args()

    job_start = datetime.now().isoformat()

    # ── 0. 初始化 & 文件检查 ──
    db_path = args.db
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 检查必需的数据文件
    required_files = {
        "schema": args.schema,
        "aliases": args.aliases,
        "tournaments": DEFAULT_TOURNAMENTS,
        "source_manifest": DEFAULT_SOURCE_MANIFEST,
    }
    missing = []
    for name, path in required_files.items():
        if not Path(path).exists():
            missing.append(f"  [{name}] {path}")
    if missing:
        print("[错误] 以下必需文件不存在:", file=sys.stderr)
        for m in missing:
            print(m, file=sys.stderr)
        sys.exit(1)

    print(f"{'='*60}")
    print(f"  世界杯数据导入 v2")
    print(f"{'='*60}")

    # 建表
    print(f"\n[1/8] 建表...")
    create_tables(db_path, args.schema)
    print(f"  数据库: {db_path}")

    # ── 1. 导入 tournament ──
    print(f"\n[2/8] 导入 tournament 数据...")
    t_count = import_tournaments_from_json(db_path, DEFAULT_TOURNAMENTS)
    print(f"  已导入 {t_count} 届世界杯")

    # ── 2. 导入球队 ──
    print(f"\n[3/8] 导入球队...")
    team_count = import_teams_from_aliases(db_path, args.aliases)
    alias_count = import_team_aliases(db_path, args.aliases)
    print(f"  已导入 {team_count} 支球队, {alias_count} 条别名")

    # ── 3. 导入来源 ──
    print(f"\n[4/8] 导入数据来源...")
    s_count = import_sources_from_manifest(db_path, DEFAULT_SOURCE_MANIFEST)
    print(f"  已导入 {s_count} 个数据来源")

    # ── 4. 读取并注册输入文件 ──
    print(f"\n[5/8] 读取原始数据: {args.input}")
    if args.source_type == "csv":
        from services.data_importer import KAGGLE_MATCH_MAP
        raw_records = import_csv(args.input, field_map=KAGGLE_MATCH_MAP)
        # Kaggle 预处理
        raw_records = _preprocess_kaggle(raw_records)
    else:
        raw_records = import_json(args.input)

    print(f"  原始记录数: {len(raw_records)}")

    # 注册输入文件来源
    checksum = compute_checksum(args.input)
    file_source_id = generate_source_id(args.source_type, Path(args.input).stem)
    file_source = Source(
        source_id=file_source_id,
        title=Path(args.input).name,
        source_url=f"https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset",
        source_type=args.source_type,
        publisher="Kaggle (Jahaidul Islam)",
        retrieved_at=job_start[:10],
        checksum=checksum,
        license_info="CC0: Public Domain",
    )
    insert_source(db_path, file_source)

    # ── 5. 清洗 ──
    print(f"\n[6/8] 清洗数据...")
    alias_data = load_team_aliases(args.aliases)
    cleaned_matches = []
    total_report = CleaningReport(total_records=len(raw_records))
    reset_match_counter()

    for i, record in enumerate(raw_records):
        cleaned, report = clean_match_record(
            record, alias_data,
            source_ids=[file_source_id, "source-kaggle-001"],
        )
        if cleaned:
            cleaned_matches.append(cleaned)
        total_report.valid += report.valid
        total_report.fixed += report.fixed
        total_report.rejected += report.rejected
        total_report.warnings.extend(report.warnings)
        total_report.errors.extend(report.errors)

        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(raw_records)}")

    print(f"  有效: {total_report.valid}, 修复: {total_report.fixed}, "
          f"拒绝: {total_report.rejected}")

    # ── 6. 写入数据库 ──
    print(f"\n[7/8] 写入数据库...")
    if cleaned_matches:
        match_objects = [_dict_to_match(m) for m in cleaned_matches]
        inserted = bulk_insert_matches(db_path, match_objects)
        print(f"  已写入 {inserted} 场比赛")

        # 建立 match_sources 关联
        for m in match_objects:
            for sid in [file_source_id, "source-kaggle-001"]:
                ms = MatchSource(
                    match_id=m.match_id,
                    source_id=sid,
                    evidence_type="primary" if sid == file_source_id else "cross_check",
                    is_primary=1 if sid == file_source_id else 0,
                )
                insert_match_source(db_path, ms)

    # 保存清洗报告
    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(total_report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── 7. 记录导入任务 ──
    job = ImportJob(
        job_type="full_import",
        source_file=args.input,
        records_total=len(raw_records),
        records_valid=total_report.valid,
        records_fixed=total_report.fixed,
        records_rejected=total_report.rejected,
        started_at=job_start,
        completed_at=datetime.now().isoformat(),
        data_version="2026-07-16-v2",
        notes="v2 导入：英文阶段枚举 + tournament 范围校验 + penalty_score 分离",
    )
    from services.db_schema import insert_import_job
    insert_import_job(db_path, job)

    # ── 8. 生成事实文本（C → D 接口：match_facts.jsonl）──
    print(f"\n[8/8] 生成事实文本 (C → D Chroma 入库格式)...")
    all_matches = query_all_matches(db_path)
    all_teams = {t.team_id: t for t in query_all_teams(db_path)}

    # 主来源的 URL
    source_url = "https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset"

    facts = generate_all_match_facts(
        all_matches, all_teams,
        source_ids=[file_source_id, "source-kaggle-001"],
        source_url=source_url,
        source_page=None,
    )

    # 输出 JSONL（D 的 Chroma 直接消费）
    jsonl_path = write_match_facts_jsonl(facts, args.output_facts)
    print(f"  事实文本 (JSONL): {jsonl_path} ({len(facts)} 条)")

    # 输出 JSON（便于人工查阅）
    json_path = write_match_facts_json(facts, args.output_facts_json)
    print(f"  事实文本 (JSON):  {json_path}")

    # ── 统计 ──
    print(f"\n{'='*60}")
    print(f"  导入完成")
    print(f"{'='*60}")
    counts = count_records(db_path)
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print(f"\n数据库: {db_path}")
    print(f"事实文本: {jsonl_path}")
    print(f"清洗报告: {report_path}")


def _dict_to_match(d: dict) -> Match:
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
        city=d.get("city", ""),
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


def _preprocess_kaggle(records: list[dict]) -> list[dict]:
    """预处理 Kaggle 数据集。"""
    processed = []
    for rec in records:
        r = dict(rec)
        for key in ("home_score_90", "away_score_90"):
            val = str(r.get(key, "0")).strip()
            try:
                r[key] = int(val)
            except ValueError:
                r[key] = 0

        is_shootout = str(r.get("penalty_shootout_flag", "0")).strip() == "1"
        for key in ("home_penalties", "away_penalties"):
            val = str(r.get(key, "0")).strip()
            if is_shootout:
                try:
                    r[key] = int(val)
                except ValueError:
                    r[key] = None
            else:
                r[key] = None

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
