"""更新 score_display 和 penalty_score 字段"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from services.db_schema import get_connection

db = "data/worldcup_v2.db"
conn = get_connection(db)

fixed = conn.execute("""
    SELECT * FROM matches
    WHERE result_type IN ('extra_time', 'penalties')
""").fetchall()

for m in fixed:
    h90, a90 = m["home_score_90"], m["away_score_90"]
    het, aet = m["home_score_et"], m["away_score_et"]
    hpen, apen = m["home_penalties"], m["away_penalties"]
    rt = m["result_type"]

    if rt == "extra_time":
        new_display = f"{het}:{aet}"
        new_penalty = ""
    elif rt == "penalties":
        new_display = f"{het or h90}:{aet or a90}"
        new_penalty = f"{hpen or 0}:{apen or 0}"
    else:
        continue

    conn.execute("""
        UPDATE matches SET score_display = ?, penalty_score = ?
        WHERE match_id = ?
    """, (new_display, new_penalty, m["match_id"]))

conn.commit()

# 验证关键比赛
for mid in ["M-2022-64", "M-2014-64"]:
    f = conn.execute("SELECT * FROM matches WHERE match_id = ?", (mid,)).fetchone()
    if f:
        d = dict(f)
        print(f"{mid} ({d['tournament_year']}): "
              f"90={d['home_score_90']}:{d['away_score_90']} "
              f"ET={d['home_score_et']}:{d['away_score_et']} "
              f"pen={d.get('penalty_score','')} "
              f"display={d['score_display']} "
              f"result={d['result_type']}")

conn.close()
print(f"\nTotal updated: {len(fixed)} matches")
