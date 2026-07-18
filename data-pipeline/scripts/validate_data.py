"""
数据校验脚本

检查 SQLite 数据库中的数据质量：
- 比分逻辑一致性
- 球队引用完整性
- source_id 可追溯性
- 重复 match_id
"""

import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.db_schema import query_all_matches, query_all_teams, count_records


def main(db_path: str = "data/worldcup.db"):
    if not Path(db_path).exists():
        print(f"[错误] 数据库不存在: {db_path}")
        sys.exit(1)

    print(f"===== 数据校验: {db_path} =====\n")

    matches = query_all_matches(db_path)
    teams = {t.team_id: t for t in query_all_teams(db_path)}

    issues = []
    warnings = []

    # ── 1. 比分逻辑 ──
    for m in matches:
        # regulation/extra_time 应有胜者且比分不等
        if m.result_type in ("regulation", "extra_time"):
            final_home = m.home_score_et if m.home_score_et is not None else m.home_score_90
            final_away = m.away_score_et if m.away_score_et is not None else m.away_score_90
            if final_home == final_away:
                issues.append(f"[比分逻辑] {m.match_id}: result_type={m.result_type} 但最终比分相等 {final_home}:{final_away}")
            if not m.winner_team_id:
                issues.append(f"[比分逻辑] {m.match_id}: result_type={m.result_type} 但 winner_team_id 为空")

        # draw 不能有胜者
        if m.result_type == "draw":
            if m.home_score_90 != m.away_score_90:
                issues.append(f"[比分逻辑] {m.match_id}: result_type=draw 但比分不相等")
            if m.winner_team_id:
                issues.append(f"[比分逻辑] {m.match_id}: result_type=draw 但 winner_team_id={m.winner_team_id}")

        # penalties 的正式比分必须相等
        if m.result_type == "penalties":
            final_home = m.home_score_et if m.home_score_et is not None else m.home_score_90
            final_away = m.away_score_et if m.away_score_et is not None else m.away_score_90
            if final_home != final_away:
                issues.append(f"[比分逻辑] {m.match_id}: result_type=penalties 但正式比分不相等")

        # 胜者必须是参赛方
        if m.winner_team_id and m.winner_team_id not in (m.home_team_id, m.away_team_id):
            issues.append(f"[比分逻辑] {m.match_id}: winner_team_id={m.winner_team_id} 不在参赛双方中")

    # ── 2. 球队引用 ──
    team_ids = set(teams.keys())
    for m in matches:
        if m.home_team_id not in team_ids:
            issues.append(f"[球队引用] {m.match_id}: home_team_id={m.home_team_id} 不在 teams 表中")
        if m.away_team_id not in team_ids:
            issues.append(f"[球队引用] {m.match_id}: away_team_id={m.away_team_id} 不在 teams 表中")

    # ── 3. 重复 match_id ──
    match_ids = [m.match_id for m in matches]
    duplicates = [mid for mid, count in Counter(match_ids).items() if count > 1]
    if duplicates:
        issues.append(f"[重复] 发现 {len(duplicates)} 个重复 match_id: {duplicates[:5]}...")

    # ── 4. source 关联检查 ──
    # (v2: source_id 已从 Match 实体移至 match_sources 关联表)
    try:
        from services.db_schema import get_connection
        conn = get_connection(db_path)
        ms_count = conn.execute("SELECT COUNT(*) as n FROM match_sources").fetchone()["n"]
        conn.close()
        if ms_count == 0:
            warnings.append(f"[来源] match_sources 关联表为空，比赛可能未关联来源")
    except Exception:
        pass  # 旧版数据库可能没有 match_sources 表

    # ── 5. 统计 ──
    result_types = Counter(m.result_type for m in matches)
    stages = Counter(m.stage for m in matches)

    print(f" 总记录数:    {count_records(db_path)}")
    print(f" 比赛数:      {len(matches)}")
    print(f" 结果类型分布: {dict(result_types)}")
    print(f" 阶段分布:     {dict(stages)}")
    print(f" 球队数:       {len(teams)}")

    if issues:
        print(f"\n  ❌ 错误 ({len(issues)} 条):")
        for issue in issues:
            print(f"     {issue}")
    else:
        print(f"\n  ✅ 未发现数据逻辑错误")

    if warnings:
        print(f"\n  ⚠️ 警告 ({len(warnings)} 条):")
        for w in warnings:
            print(f"     {w}")

    # 输出 JSON 报告
    report = {
        "total_matches": len(matches),
        "total_teams": len(teams),
        "result_types": dict(result_types),
        "stages": dict(stages),
        "issues": issues,
        "warnings": warnings,
    }
    report_path = Path("data/validation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n校验报告已保存: {report_path}")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/worldcup.db")
    args = parser.parse_args()
    main(args.db)
