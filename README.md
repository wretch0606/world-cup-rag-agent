# D 成员 — Chroma 检索

> 来自 C（数据工程）的交付 | 2026-07-16

## 交付文件

| 文件 | 用途 |
|------|------|
| `match_facts.jsonl` | 964 条标准化事实文本，每行一个 JSON，直接导入 Chroma |
| `team_aliases.json` | 85 支球队别名（metadata 过滤用） |
| `source_manifest.json` | 数据来源清单 |
| `01-C-to-D-Chroma入库接口契约.md` | C→D 入库格式规范 |
| `02-D-to-E-检索结果接口契约.md` | D→E 输出格式规范 |

## 你需要做的

1. **导入 Chroma**：`match_facts.jsonl` 每行的 `id` 字段作为 upsert key
2. **确认 `team_ids` 存储方式**：如果 Chroma 版本不支持数组，序列化为 `"team_ARG,team_FRA"` 逗号分隔
3. **metadata 过滤**：支持 `years`、`team_ids`、`stages`、`result_types`、`match_ids`
4. **检索结果必须透传**：`source_id`、`source_url`、`source_page`、`data_version` 原样回到 E
5. **不生成答案**：D 只返回 candidates + 评分，答案由 E 生成

## match_facts.jsonl 格式

```json
{
  "id": "match_fact_M-2022-64_v2",
  "text": "2022年世界杯决赛，阿根廷队...",
  "metadata": {
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "stage": "决赛",
    "team_ids": ["team_ARG", "team_FRA"],
    "result_type": "penalties",
    "source_id": "src_csv_20260716_001",
    "document_name": "FIFA World Cup 2022",
    "source_url": "https://www.kaggle.com/datasets/...",
    "source_page": null,
    "chunk_index": 0,
    "language": "zh",
    "data_version": "2026-07-16-v2"
  }
}
```

## 检索结果示例

见 `02-D-to-E-检索结果接口契约.md` 第 2 节。
