# 02 — D → E：检索结果接口契约 v2.0

## 0. 文档状态

| 项目 | 内容 |
|------|------|
| 契约版本 | `retrieval-v2.0` |
| 方向 | D（Chroma 检索）→ E（RAG 生成与评测） |
| 前提 | D 已完成 Chroma 入库，Retrieval Service 就绪 |

## 1. 核心原则

- D **不生成最终自然语言答案**
- D 返回检索候选列表 + 评分元数据
- E 接收候选列表，结合 SQL 结构化事实做融合和生成
- D 必须返回实际执行状态（rewrite 是否成功、reranker 是否可用），不能只回显请求开关

## 2. 完整示例

```json
{
  "query": "2022年世界杯决赛结果是什么？",
  "rewritten_query": "2022 世界杯 决赛 阿根廷 法国 正式比分 点球比分",
  "filters": {
    "tournament_year": 2022,
    "stage": "决赛"
  },
  "config": {
    "top_k": 10,
    "reranker_enabled": true
  },
  "candidates": [
    {
      "text": "2022年世界杯决赛，阿根廷与法国在加时赛后3:3战平，点球大战阿根廷4:2获胜。",
      "vector_score": 0.83,
      "rerank_score": 0.96,
      "retrieval_rank": 3,
      "rerank_rank": 1,
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
  ],
  "execution": {
    "rewrite_applied": true,
    "reranker_applied": true,
    "warnings": [],
    "timing": {
      "rewrite_ms": 30,
      "retrieval_ms": 60,
      "rerank_ms": 110,
      "total_ms": 200
    }
  }
}
```

## 3. 字段说明

### 3.1 顶层

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `query` | string | ✅ | E 传入的原始查询 |
| `rewritten_query` | string | | D 改写后的查询（未改写则为 null） |
| `filters` | object | | 实际应用的 Chroma metadata 过滤条件 |
| `config` | object | | 实际使用的检索配置 |
| `candidates` | Candidate[] | ✅ | 检索候选列表，按 rerank_score 降序 |
| `execution` | object | ✅ | 实际执行状态（非回显） |

### 3.2 Candidate（来自 Chroma 的 EvidenceItem）

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `text` | string | ✅ | 检索到的文本片段 |
| `vector_score` | number | | 向量距离/相似度，越小越相关 |
| `rerank_score` | number/null | | Reranker 分数，越大越相关；未启用为 null |
| `retrieval_rank` | integer | | 向量召回排序位置 |
| `rerank_rank` | integer/null | | Reranker 排序后位置 |
| `metadata` | object | ✅ | Chroma 中存储的 metadata（原样透传） |

### 3.3 metadata（必须透传字段）

这些字段从 C 的入库记录来，D 原样带回：

| 字段 | 说明 |
|------|------|
| `match_id` | 关联的比赛 ID |
| `tournament_year` | 年份过滤用 |
| `stage` | 阶段过滤用 |
| `team_ids` | 球队过滤用 |
| `result_type` | 结果类型过滤用 |
| `source_id` | **必须保留**，进入最终响应 |
| `source_url` | 来源 URL |
| `source_page` | 页码 |
| `document_name` | 文档名 |
| `data_version` | 数据版本 |

## 4. 降级策略

| 场景 | 行为 | status |
|------|------|--------|
| Rewrite 失败 | 用原 query 继续检索 | `degraded` |
| Reranker 失败 | 用 vector_score 排序 | `degraded` |
| 无候选 | 返回空 candidates | `empty` |
| 完全失败 | 返回 error | `error` |

## 5. E 的接收处理

E 收到后需要做的：
1. 将 candidates 与 B 传入的 StructuredFact 做交叉校验
2. 冲突时以 StructuredFact 为准，产生 SOURCE_CONFLICT 告警
3. 去重后选择实际进入生成上下文的 evidence
4. `source_id`、`source_url` 等来源信息原样放入最终 RAGResult.sources

## 6. D 的确认清单

- [ ] Query Rewrite 和 Reranker 实现完成且可独立开关
- [ ] metadata 过滤支持 years、team_ids、stages、result_types、match_ids
- [ ] vector_score 和 rerank_score 的方向和空值规则明确
- [ ] retrieval_rank 和 rerank_rank 双排序返回
- [ ] source_id、source_url、source_page、data_version 在检索结果中原样透传
- [ ] 降级场景均有日志和告警
