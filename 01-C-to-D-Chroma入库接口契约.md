# 01 — C → D：Chroma 入库接口契约 v2.0

## 0. 文档状态

| 项目 | 内容 |
|------|------|
| 契约版本 | `ingest-v2.0` |
| 方向 | C（数据工程）→ D（Chroma 检索） |
| 文件格式 | `match_facts.jsonl`（每行一个 JSON） |
| 前提 | C 已完成 P0 数据修正，D 已建好 Chroma Collection |

## 1. 单条记录格式

```json
{
  "id": "match_fact_M-2018-64_v1",
  "text": "2018年世界杯决赛，法国队与克罗地亚队的正式比分为4:2，法国队在常规时间获胜。",
  "metadata": {
    "match_id": "M-2018-64",
    "tournament_year": 2018,
    "stage": "决赛",
    "team_ids": ["team_FRA", "team_CRO"],
    "result_type": "regulation",

    "source_id": "src_csv_20260716_001",
    "document_name": "FIFA World Cup 2018",
    "source_url": "https://www.kaggle.com/datasets/...",
    "source_page": null,

    "chunk_index": 0,
    "language": "zh",
    "data_version": "2026-07-16-v2"
  }
}
```

## 2. 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `id` | string | ✅ | 幂等更新 key，格式 `match_fact_{match_id}_{version}` |
| `text` | string | ✅ | 被向量化的中文事实文本，80-200 字 |
| `metadata.match_id` | string | ✅ | 与 C/B/D 一致的比赛 ID |
| `metadata.tournament_year` | integer | ✅ | 世界杯年份 |
| `metadata.stage` | string | ✅ | 中文阶段名（用于 Chroma 过滤） |
| `metadata.team_ids` | string[] | ✅ | 双方球队 ID 数组 |
| `metadata.result_type` | string | ✅ | regulation / extra_time / penalties / draw |
| `metadata.source_id` | string | ✅ | **必须保留**到最终响应的来源 ID |
| `metadata.document_name` | string | ✅ | 人类可读的文档名 |
| `metadata.source_url` | string/null | | 公开可访问的来源 URL |
| `metadata.source_page` | number/null | | PDF 页码，非 PDF 为 null |
| `metadata.chunk_index` | integer | | 长文档切片序号，单场比赛固定为 0 |
| `metadata.language` | string | | 固定 "zh" |
| `metadata.data_version` | string | ✅ | 数据版本号，支持实验复现和增量更新 |

## 3. 幂等要求

- 重复导入同一条 `id` 的记录，Chroma 应执行 upsert 而非 insert
- `id` 变更规则：内容变化 → 更新版本号 → 新 id；纯格式修正 → 同 id 覆盖
- C 在数据更新后必须通知 D 执行同步（全量或增量）

## 4. team_ids 兼容说明

当前 Chroma 版本对数组类型 metadata 的支持因版本而异：
- 支持数组的版本：直接使用 `["team_FRA", "team_CRO"]`
- 不支持的版本：序列化为逗号分隔字符串 `"team_FRA,team_CRO"`

D 需确认并用对应方式消费。

## 5. D 的确认清单

- [ ] Chroma Collection 的 metadata schema 与上述字段对齐
- [ ] 确认 `team_ids` 的存储方式（数组 or 字符串）
- [ ] 确认 `source_id`、`source_url`、`source_page` 会在检索结果中原样返回
- [ ] 确认 `data_version` 会在 EvidenceItem 中透传
- [ ] 确认增量更新的策略（按 data_version + match_id 过滤）
