# 版本说明

## 当前版本

**v2.0** — 2026-07-16

## 数据来源

| 来源 | URL | 用途 |
|------|-----|------|
| Kaggle: FIFA World Cup 1930-2022 All Match Dataset | `https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset` | 964 场比赛基础数据 |
| Kaggle: FIFA World Cup All Goals 1930-2022 | 同上作者 | 2720 条进球事件（用于交叉校验和比分修正） |
| FIFA 官网 | `https://www.fifa.com/en/tournaments/mens/worldcup` | 届次信息交叉参考 |
| Wikipedia | `https://en.wikipedia.org/wiki/FIFA_World_Cup` | 届次信息交叉参考 |

## v1 → v2 主要变更

### 数据修正
- **比分口径修正**: 73 场加时/点球比赛中，61 场自动修正了 90 分钟比分（通过 goals 数据减去加时进球）。12 场无进球数据的比赛保持原值，标记待人工复核。
- **2022 决赛**: `score_90: 3:3 → 2:2`，`score_et: NULL → 3:3`
- **2014 决赛**: `score_90: 1:0 → 0:0`，`score_et: NULL → 1:0`

### Schema 变更
- `tournaments` 表：从 1 条扩展为 22 条完整记录，新增 `host_en`、`champion`、`top_scorer` 字段
- `matches` 表：`stage` 改为英文枚举（`final` 而非 `决赛`），新增 `stage_name`、`tournament_id`、`raw_match_date`、`penalty_score`、`city`；移除 `source_id`（迁至 `match_sources`）
- `goals` 表：`team_id` 从 `T-XX` 格式统一为 `team_XXX`，新增 `source_team_id` 保留旧值
- 新增表：`team_aliases`、`match_sources`、`import_jobs`、`audit_logs`、`documents`

### 接口变更
- `match_facts.jsonl` 格式改为 Chroma 标准摄入格式：`{id, text, metadata: {source_url, source_page, chunk_index}}`
- 阶段枚举：DB 和 API 使用英文，中文显示名通过 `stage_name` 字段

## 已知限制
1. 12 场加时/点球比赛无进球数据，90 分钟比分未自动修正（清单见 `backend/data/score_fix_report.json`）
2. 点球大战逐轮数据缺失（goals 中无 `match_period='penalties'` 记录）
3. 数据来源于 Kaggle 公开数据集，未与 FIFA 官方记录逐场交叉校验
4. `world_cup_reports` collection 的 PDF/网页文本未导入

## 重建方法

在新环境中重建 v2 数据库：

```bash
# 1. 确保原始数据文件在 raw_data/ 目录下：
#    - FIFA World Cup 1930-2022 All Match Dataset.csv
#    - FIFA World Cup All Goals 1930-2022.csv (可选，用于比分修正)

# 2. 运行导入
python scripts/import_data_v2.py \
  --input raw_data/FIFA\ World\ Cup\ 1930-2022\ All\ Match\ Dataset.csv \
  --source_type csv

# 3. 导入进球数据并修正比分
python scripts/build_goals_team_map.py
python scripts/fix_match_scores.py
python scripts/update_score_display.py

# 4. 运行校验
python scripts/validate_data_v2.py

# 5. 交付文件在 backend/data/ 目录下
```

## 交付清单

| 文件 | 路径 | 状态 |
|------|------|:--:|
| 数据库 | `backend/data/worldcup_v2.db` | ✅ |
| 建表脚本 | `backend/data/schema.sql` | ✅ |
| 数据字典 | `数据字典.md` | ✅ |
| 导入脚本 | `scripts/import_data_v2.py` | ✅ |
| 校验报告 | `backend/data/validation_report.md` | ✅ |
| 来源清单 | `backend/data/source_manifest.json` | ✅ |
| 事实文本 | `backend/data/match_facts.jsonl` | ✅ |
| 球队别名 | `backend/data/team_aliases.json` | ✅ |
| 比分修正报告 | `backend/data/score_fix_report.json` | ✅ |
| 清洗报告 | `backend/data/cleaning_report.json` | ✅ |
| 版本说明 | `VERSION.md` | ✅ |
