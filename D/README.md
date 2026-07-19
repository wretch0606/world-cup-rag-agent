# D 成员 — Chroma 检索

> 来自 C（数据工程）的交付 | 2026-07-19 | 契约版本 ingest-v2.1

## 交付文件

| 文件 | 用途 |
|------|------|
| `match_facts.jsonl` | 964 条标准化事实文本，每行一个 JSON，直接导入 Chroma |
| `match_facts.json` | 同上（美化格式，人工查阅用） |
| `team_aliases.json` | 85 支球队别名（metadata 过滤用） |
| `source_manifest.json` | 数据来源清单 |
| `stage_mapping.json` | stage 英文 enum ↔ 中文显示名 |
| `score_fix_report.json` | 比分修正记录（61 场自动修正 + 12 场需人工确认） |
| `01-C-to-D-Chroma入库接口契约.md` | **v2.1** — 必须看，字段有变更 |
| `数据字典.md` | 全部字段说明 |

## ⚠️ v2.0 → v2.1 字段变更

| 变更 | 旧 | 新 |
|------|----|----|
| 来源字段 | `source_id: "..."` (单值) | `source_ids: ["...", "..."]` (数组) |
| 阶段字段 | `stage: "决赛"` (中文) | `stage: "final"` (英文 enum) |
| 阶段中文 | 无 | `stage_name: "决赛"` (新增) |

**D 的过滤代码需要用 `metadata.stage`（英文）做过滤，不再用中文。**

## match_facts.jsonl 格式

```json
{
  "id": "match_fact_M-2022-64_2026-07-16-v2",
  "text": "2022年世界杯决赛，阿根廷队在Lusail Stadium与法国队90分钟内2:2战平、加时赛后3:3仍战平，点球大战阿根廷队4:2胜出晋级。",
  "metadata": {
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "stage": "final",
    "stage_name": "决赛",
    "team_ids": ["team_ARG", "team_FRA"],
    "result_type": "penalties",
    "source_ids": ["src_csv_20260719_001", "source-kaggle-001"],
    "document_name": "FIFA World Cup 2022",
    "source_url": "https://www.kaggle.com/datasets/...",
    "source_page": null,
    "chunk_index": 0,
    "language": "zh",
    "data_version": "2026-07-16-v2"
  }
}
```

## 你需要做的

1. **按 v2.1 契约适配 metadata schema**：`source_ids` 数组 + `stage` 英文 enum + `stage_name`
2. **导入 Chroma**：`id` 字段作为 upsert key，重复导入应覆盖
3. **metadata 过滤用英文值**：`stages: ["final", "semi_final"]`，不用 `["决赛"]`
4. **检索结果透传**：`source_ids`、`source_url`、`source_page`、`data_version` 原样到 E
5. **不生成答案**：D 只返回 candidates + 评分

## 数据质量

- 964 场全部通过清洗（0 拒绝）
- 73 场加时/点球比赛比分已修正：61 场自动 + 12 场 0:0 人工确认
- data_version: `2026-07-16-v2`
