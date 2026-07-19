"""
从 goals CSV 的 team_name 构建旧 T-XX → 新 team_XXX 映射。

用法: python scripts/build_goals_team_map.py
输出: data/goals_team_map.json
"""

import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from services.data_cleaner import load_team_aliases, normalize_team_name

GOALS_PATH = "raw_data/FIFA World Cup All Goals 1930-2022.csv"
ALIAS_PATH = "data/team_aliases.json"
OUTPUT = "data/goals_team_map.json"


def main():
    alias_data = load_team_aliases(ALIAS_PATH)
    alias_map = alias_data["alias_map"]

    # 读取 goals，收集所有 team_id → team_name 配对
    pairs = {}
    for enc in ["utf-8-sig", "latin-1"]:
        try:
            with open(GOALS_PATH, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    old_id = row["team_id"].strip()
                    name = row["team_name"].strip()
                    if old_id and old_id not in pairs:
                        pairs[old_id] = name
            break
        except UnicodeError:
            continue

    print(f"发现 {len(pairs)} 个旧 team_id")

    # 构建映射
    mapping = {}
    unmatched = []
    for old_id, name in sorted(pairs.items()):
        new_id, warn = normalize_team_name(name, alias_map)
        if new_id:
            mapping[old_id] = {
                "new_team_id": new_id,
                "team_name": name,
                "match_method": warn or "exact",
            }
        else:
            unmatched.append({"old_id": old_id, "name": name})

    print(f"映射成功: {len(mapping)}")
    if unmatched:
        print(f"未匹配: {len(unmatched)}")
        for u in unmatched:
            print(f"  {u['old_id']}: {u['name']}")

    # 输出
    output = {
        "mapping": mapping,
        "unmatched": unmatched,
        "_note": "旧 T-XX → 新 team_XXX 映射，用于 goals.team_id 统一",
    }
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {OUTPUT}")


if __name__ == "__main__":
    main()
