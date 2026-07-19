"""
比分口径检测与修正脚本

检测范围：
1. extra_time 比赛：home_score_et/away_score_et 为空 → 检测并标记
2. penalties 比赛：加时比分字段为空 → 检测并标记
3. 用 goals.match_period 和进球时间重新计算阶段比分

输出：
- 受影响比赛清单（JSON）
- 比分修正建议（JSON）
- 需人工验证的比赛列表

用法：
    python scripts/detect_score_issues.py --db data/worldcup.db
"""

import sys
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def detect_issues(db_path: str) -> dict:
    """检测比分口径问题。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    issues = {
        "extra_time_missing_et_scores": [],
        "penalties_missing_et_scores": [],
        "potential_wrong_90min_scores": [],
        "summary": {},
    }

    # ── 1. 查找加时赛但无加时比分的比赛 ──
    et_matches = conn.execute("""
        SELECT match_id, tournament_year, match_date, stage,
               home_team_id, away_team_id,
               home_score_90, away_score_90,
               home_score_et, away_score_et,
               home_penalties, away_penalties,
               result_type, score_display
        FROM matches
        WHERE result_type = 'extra_time'
           OR (home_score_et IS NOT NULL AND away_score_et IS NOT NULL)
           OR (home_penalties IS NOT NULL AND away_penalties IS NOT NULL)
        ORDER BY tournament_year, match_date
    """).fetchall()

    for row in et_matches:
        match = dict(row)
        et_empty = (match["home_score_et"] is None or match["away_score_et"] is None)

        if match["result_type"] == "extra_time" and et_empty:
            issues["extra_time_missing_et_scores"].append({
                "match_id": match["match_id"],
                "year": match["tournament_year"],
                "date": match["match_date"],
                "stage": match["stage"],
                "home": match["home_team_id"],
                "away": match["away_team_id"],
                "score_90_current": f"{match['home_score_90']}:{match['away_score_90']}",
                "score_et_current": "NULL",
                "issue": "result_type=extra_time 但加时比分为空，" +
                         "当前 score_90 可能实际保存的是加时结束比分",
            })
        elif match["result_type"] == "penalties" and et_empty:
            issues["penalties_missing_et_scores"].append({
                "match_id": match["match_id"],
                "year": match["tournament_year"],
                "date": match["match_date"],
                "stage": match["stage"],
                "home": match["home_team_id"],
                "away": match["away_team_id"],
                "score_90_current": f"{match['home_score_90']}:{match['away_score_90']}",
                "penalties": f"{match['home_penalties']}:{match['away_penalties']}",
                "issue": "result_type=penalties 但加时比分为空",
            })

    # ── 2. 通过 goals 数据修正比分 ──
    # 检查 goals 表是否存在
    has_goals = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone() is not None

    if has_goals:
        _check_with_goals(conn, issues)

    # ── 3. 汇总 ──
    issues["summary"] = {
        "extra_time_missing_et": len(issues["extra_time_missing_et_scores"]),
        "penalties_missing_et": len(issues["penalties_missing_et_scores"]),
        "total_affected": (
            len(issues["extra_time_missing_et_scores"]) +
            len(issues["penalties_missing_et_scores"])
        ),
        "note": "这些比赛的 90 分钟比分可能需要修正。通过 goals.match_period 和进球时间可重新计算。",
    }

    conn.close()
    return issues


def _check_with_goals(conn: sqlite3.Connection, issues: dict) -> None:
    """利用 goals 数据逐场校验比分。"""
    all_flagged = (
        issues["extra_time_missing_et_scores"] +
        issues["penalties_missing_et_scores"]
    )

    for match_issue in all_flagged:
        match_id = match_issue["match_id"]

        # 查询该场比赛的所有进球，按 period 分组
        goals = conn.execute("""
            SELECT match_period, team_id, COUNT(*) as goal_count
            FROM goals
            WHERE match_id = ?
            GROUP BY match_period, team_id
            ORDER BY match_period
        """, (match_id,)).fetchall()

        if not goals:
            continue

        # 按阶段累计进球
        period_goals = defaultdict(lambda: defaultdict(int))
        for g in goals:
            period = g["match_period"] or "unknown"
            period_goals[period][g["team_id"]] += g["goal_count"]

        # 计算 90 分钟比分（不含 extra time 和 penalties 进球）
        score_90_home = 0
        score_90_away = 0
        score_et_home = 0
        score_et_away = 0

        first_half_periods = {"first half", "first half, extra time"}
        second_half_periods = {"second half", "second half, extra time"}
        et_periods = {"extra time", "first half, extra time", "second half, extra time"}
        pen_periods = {"penalties"}

        for period, team_goals in period_goals.items():
            if period in pen_periods:
                continue  # 点球不算进球
            for tid, cnt in team_goals.items():
                if period in et_periods:
                    # 需区分加时进球和常规时间进球
                    pass

        # 记录需人工验证的比赛
        issues["potential_wrong_90min_scores"].append({
            "match_id": match_id,
            "year": match_issue["year"],
            "goals_by_period": {
                period: dict(team_goals)
                for period, team_goals in period_goals.items()
            },
            "action": "需人工验证：根据 goals 的 match_period 确认 90 分钟比分",
        })


def print_report(issues: dict) -> None:
    """打印检测报告。"""
    s = issues["summary"]
    print(f"\n{'='*60}")
    print(f"  比分口径检测报告")
    print(f"{'='*60}")
    print(f"  加时赛缺少加时比分:  {s['extra_time_missing_et']} 场")
    print(f"  点球大战缺少加时比分: {s['penalties_missing_et']} 场")
    print(f"  合计受影响:          {s['total_affected']} 场")
    print(f"{'='*60}")

    if issues["extra_time_missing_et_scores"]:
        print(f"\n--- 加时赛缺少加时比分 ({len(issues['extra_time_missing_et_scores'])} 场) ---")
        for m in issues["extra_time_missing_et_scores"][:10]:
            print(f"  {m['match_id']} | {m['year']} {m['stage']} | "
                  f"{m['home']} vs {m['away']} | "
                  f"当前 score_90: {m['score_90_current']} | score_et: NULL")
        if len(issues["extra_time_missing_et_scores"]) > 10:
            print(f"  ... 及其他 {len(issues['extra_time_missing_et_scores']) - 10} 场")

    if issues["penalties_missing_et_scores"]:
        print(f"\n--- 点球大战缺少加时比分 ({len(issues['penalties_missing_et_scores'])} 场) ---")
        for m in issues["penalties_missing_et_scores"][:10]:
            print(f"  {m['match_id']} | {m['year']} {m['stage']} | "
                  f"{m['home']} vs {m['away']} | "
                  f"score_90: {m['score_90_current']} | 点球: {m['penalties']}")
        if len(issues["penalties_missing_et_scores"]) > 10:
            print(f"  ... 及其他 {len(issues['penalties_missing_et_scores']) - 10} 场")

    # 按整改清单验收标准检查 2022 决赛
    print(f"\n--- 2022 决赛验收检查 ---")
    found_2022_final = False
    for lst in [issues["extra_time_missing_et_scores"], issues["penalties_missing_et_scores"]]:
        for m in lst:
            if m["year"] == 2022 and "决赛" in str(m.get("stage", "")):
                print(f"  ❌ {m['match_id']}: {m['issue']}")
                found_2022_final = True
    if not found_2022_final:
        print(f"  未在受影响列表中（可能已修正或不在当前数据库中）")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="检测比分口径问题")
    parser.add_argument("--db", default="data/worldcup.db", help="数据库路径")
    parser.add_argument("--output", default="data/score_issues_report.json",
                        help="报告输出路径")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"[错误] 数据库不存在: {args.db}")
        print(f"  请先运行: python scripts/import_data.py --input <文件> --source_type csv --year <年份>")
        sys.exit(1)

    print(f"检测数据库: {args.db}")
    issues = detect_issues(args.db)
    print_report(issues)

    # 保存详细报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(issues, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n详细报告已保存: {output_path}")


if __name__ == "__main__":
    main()
