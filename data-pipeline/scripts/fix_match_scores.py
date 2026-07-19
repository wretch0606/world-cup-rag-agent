"""
比分修正脚本

用 goals.match_period 数据重新计算 73 场加时/点球比赛的：
- 90 分钟真实比分
- 加时结束累计比分
- 点球大战比分

原理：
- extra_time 比赛：当前 home_score_90 实际是加时结束比分，
  减去 goals 中 match_period 含 'extra time' 的进球数，得到真正的 90 分钟比分
- penalties 比赛：同理，且 90 分钟比分应等于加时结束比分（点球前平局）
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from services.db_schema import get_connection


def fix_scores(db_path: str) -> dict:
    """修正所有 affected 比赛的比分并写入 audit_logs。"""
    conn = get_connection(db_path)
    report = {"fixed": [], "log": []}

    # 获取所有 extra_time 和 penalties 比赛
    affected = conn.execute("""
        SELECT * FROM matches
        WHERE result_type IN ('extra_time', 'penalties')
        ORDER BY tournament_year, match_date
    """).fetchall()

    for match in affected:
        match_id = match["match_id"]
        home_id = match["home_team_id"]
        away_id = match["away_team_id"]

        # 获取该场比赛所有进球（非点球大战，非乌龙）
        goals = conn.execute("""
            SELECT team_id, match_period, COUNT(*) as cnt
            FROM goals
            WHERE match_id = ? AND match_period != 'penalties'
            GROUP BY team_id, match_period
        """, (match_id,)).fetchall()

        if not goals:
            report["log"].append(f"{match_id}: 无进球数据，跳过")
            continue

        # 按阶段累计进球（区分主客队）
        goals_90_home = 0
        goals_90_away = 0
        goals_et_home = 0
        goals_et_away = 0

        for g in goals:
            period = g["match_period"].lower()
            is_et = "extra time" in period
            if g["team_id"] == home_id:
                if is_et:
                    goals_et_home += g["cnt"]
                else:
                    goals_90_home += g["cnt"]
            elif g["team_id"] == away_id:
                if is_et:
                    goals_et_away += g["cnt"]
                else:
                    goals_90_away += g["cnt"]

        old_90_home = match["home_score_90"]
        old_90_away = match["away_score_90"]

        # 当前 90 分钟字段实际存的是加时结束比分 → 减掉加时进球
        new_90_home = old_90_home - goals_et_home
        new_90_away = old_90_away - goals_et_away
        new_et_home = old_90_home  # 当前值就是加时结束比分
        new_et_away = old_90_away

        # 更新数据库
        conn.execute("""
            UPDATE matches
            SET home_score_90 = ?, away_score_90 = ?,
                home_score_et = ?, away_score_et = ?
            WHERE match_id = ?
        """, (new_90_home, new_90_away, new_et_home, new_et_away, match_id))

        # 记录到 audit_log
        conn.execute("""
            INSERT INTO audit_logs (table_name, record_id, field_name, old_value, new_value, reason, changed_by, changed_at, data_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 'v2')
        """, ("matches", match_id, "home_score_90", str(old_90_home), str(new_90_home),
               f"修正: 减去加时进球 {goals_et_home}", "script"))

        conn.execute("""
            INSERT INTO audit_logs (table_name, record_id, field_name, old_value, new_value, reason, changed_by, changed_at, data_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 'v2')
        """, ("matches", match_id, "away_score_90", str(old_90_away), str(new_90_away),
               f"修正: 减去加时进球 {goals_et_away}", "script"))

        report["fixed"].append({
            "match_id": match_id,
            "year": match["tournament_year"],
            "stage": match["stage_name"] or match["stage"],
            "home": home_id, "away": away_id,
            "old_90": f"{old_90_home}:{old_90_away}",
            "et_goals": f"+{goals_et_home}:+{goals_et_away}",
            "new_90": f"{new_90_home}:{new_90_away}",
            "new_et": f"{new_et_home}:{new_et_away}",
            "penalties": f"{match['home_penalties']}:{match['away_penalties']}" if match["home_penalties"] else "",
        })

    conn.commit()
    conn.close()
    return report


def main():
    db_path = "data/worldcup_v2.db"

    print("Fixing match scores using goals data...")
    report = fix_scores(db_path)

    print(f"\nFixed {len(report['fixed'])} matches:")
    for r in report["fixed"]:
        pen = f" pen({r['penalties']})" if r["penalties"] else ""
        print(f"  {r['match_id']} | {r['year']} {r['stage']} | "
              f"{r['old_90']}(old) -{r['et_goals']}(et_goals) = {r['new_90']}(new_90) | "
              f"new_et={r['new_et']}{pen}")

    if report["log"]:
        print(f"\nSkipped ({len(report['log'])}):")
        for l in report["log"]:
            print(f"  {l}")

    # 输出报告
    out_path = Path("data/score_fix_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report["timestamp"] = datetime.now().isoformat()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()
