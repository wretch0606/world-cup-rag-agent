# 01 — C → D：Chroma 入库接口契约 v2.1

## 0. 文档状态

| 项目 | 内容 |
|------|------|
| 契约版本 | `ingest-v2.1` |
| 方向 | C（数据工程）→ D（Chroma 检索） |
| 文件格式 | `match_facts.jsonl`（每行一个 JSON） |
| 前提 | C 已完成 P0 数据修正，D 已建好 Chroma Collection |
| 变更摘要 | v2.0→v2.1: `source_id`→`source_ids`(数组), `stage` 改用英文 enum+`stage_name` |

## 1. 单条记录格式

```json
{
  "id": "match_fact_M-2022-64_v2",
  "text": "2022年世界杯决赛，阿根廷队在卢赛尔体育场与法国队90分钟内2:2战平、加时赛后3:3仍战平，点球大战阿根廷队4:2胜出晋级。",
  "metadata": {
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "stage": "final",
    "stage_name": "决赛",
    "team_ids": ["team_ARG", "team_FRA"],
    "result_type": "penalties",

    "source_ids": ["src_csv_20260716_001", "source-kaggle-001"],
    "document_name": "FIFA World Cup 2022",
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
| `metadata.stage` | string | ✅ | **英文枚举**，用于 Chroma 过滤，见 §6 |
| `metadata.stage_name` | string | ✅ | **v2.1新增** 中文显示名 |
| `metadata.team_ids` | string[] | ✅ | 双方球队 ID 数组 |
| `metadata.result_type` | string | ✅ | regulation / extra_time / penalties / draw |
| `metadata.source_ids` | string[] | ✅ | **v2.1变更** 多来源数组（原 `source_id` 单值） |
| `metadata.document_name` | string | ✅ | 人类可读的文档名 |
| `metadata.source_url` | string/null | | 公开可访问的来源 URL |
| `metadata.source_page` | number/null | | PDF 页码，非 PDF 为 null |
| `metadata.chunk_index` | integer | | 长文档切片序号，单场比赛固定为 0 |
| `metadata.language` | string | | 固定 "zh" |
| `metadata.data_version` | string | ✅ | 统一为 `2026-07-16-v2` |

## 6. 阶段枚举 (stage)

| 英文 enum | 中文显示 (stage_name) |
|-----------|---------------------|
| `group` | 小组赛 |
| `second_group` | 第二轮小组赛 |
| `round_of_16` | 1/8决赛 |
| `quarter_final` | 1/4决赛 |
| `semi_final` | 半决赛 |
| `third_place` | 三四名决赛 |
| `final` | 决赛 |
| `final_round` | 决赛循环赛 |

D 使用 `metadata.stage`（英文）做过滤，前端展示用 `stage_name`。

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
- [ ] 确认 `source_ids` 改为数组，fallback 兼容旧 `source_id`
- [ ] 确认 `stage` 已改为英文 enum，过滤时使用英文值
- [ ] 确认 `source_ids`、`source_url`、`source_page` 会在检索结果中原样返回
- [ ] 确认 `data_version` 会在 EvidenceItem 中透传
- [ ] 确认增量更新的策略（按 data_version + match_id 过滤）
