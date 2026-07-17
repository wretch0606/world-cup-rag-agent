"""查看数据库完整数据概览"""
import sqlite3

DB = "data/worldcup.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# 基本统计
m_cnt = conn.execute("SELECT COUNT(*) as n FROM matches").fetchone()["n"]
t_cnt = conn.execute("SELECT COUNT(*) as n FROM teams").fetchone()["n"]

years = conn.execute(
    "SELECT DISTINCT tournament_year FROM matches ORDER BY tournament_year"
).fetchall()
year_list = [str(y["tournament_year"]) for y in years]

stages = conn.execute(
    "SELECT stage, COUNT(*) as n FROM matches GROUP BY stage ORDER BY n DESC"
).fetchall()

types = conn.execute(
    "SELECT result_type, COUNT(*) as n FROM matches GROUP BY result_type"
).fetchall()

teams = conn.execute(
    "SELECT team_id, canonical_name, confederation FROM teams ORDER BY confederation, canonical_name"
).fetchall()

finals = conn.execute(
    "SELECT match_id, tournament_year, home_team_id, away_team_id, score_display, result_type FROM matches WHERE stage IN ('final','决赛','Final') ORDER BY tournament_year"
).fetchall()

print(f"总比赛: {m_cnt} 场")
print(f"总球队: {t_cnt} 支")
print(f"年份: {year_list[0]} ~ {year_list[-1]}（共 {len(year_list)} 届）")
print()

print("=== 比赛阶段 ===")
for s in stages:
    print(f"  {s['stage']}: {s['n']} 场")

print()
print("=== 结果类型 ===")
for t in types:
    print(f"  {t['result_type']}: {t['n']} 场")

print()
print("=== 球队按大洲 ===")
confs = {}
for t in teams:
    c = t["confederation"] or "其他"
    confs.setdefault(c, []).append(f"{t['canonical_name']}({t['team_id']})")
for c, tlist in sorted(confs.items()):
    names = " / ".join(tlist[:10])
    tail = "..." if len(tlist) > 10 else ""
    print(f"  {c} ({len(tlist)}支): {names}{tail}")

print()
print("=== 历届决赛 ===")
for f in finals:
    print(f"  {f['tournament_year']}: {f['home_team_id']} vs {f['away_team_id']} ({f['score_display']}) [{f['result_type']}]")

conn.close()
