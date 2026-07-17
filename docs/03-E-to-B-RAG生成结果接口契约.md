# 03 — E → B：RAG 生成结果接口契约 v2.0

## 0. 文档状态

| 项目 | 内容 |
|------|------|
| 契约版本 | `generation-v2.0` |
| 方向 | E（RAG 生成与评测）→ B（FastAPI 后端） |
| 前提 | E 已收到 D 的 RetrievalResult 和 B 的 StructuredFact |

## 1. E 的职责边界

E **负责**：

- 将 D 的检索候选与 B 的 SQL 结构化事实融合
- 生成最终自然语言答案（调用 LLM）
- 确定答案实际采用了哪些 facts、sources 和 evidence
- 检测来源冲突并生成结构化告警
- 记录生成阶段的耗时和元数据

E **不负责**：

- `graph`、`intent`、`trace_id` 的生成（这些由 B 组装）
- 前端 HTTP 响应格式组装
- Chroma 检索、Query Rewrite、Reranker
- 直接读取 SQLite 底层字段

## 2. 完整示例

```json
{
  "answer": "2022年世界杯决赛，阿根廷与法国在加时赛后战成3:3；阿根廷在点球大战中以4:2获胜。",
  "facts": [
    {
      "fact_type": "match_result",
      "match_id": "M-2022-64",
      "tournament_year": 2022,
      "stage": "final",
      "stage_name": "决赛",
      "home_team_id": "team_ARG",
      "home_team_name": "阿根廷",
      "away_team_id": "team_FRA",
      "away_team_name": "法国",
      "home_score_90": 2,
      "away_score_90": 2,
      "home_score_et": 3,
      "away_score_et": 3,
      "home_penalties": 4,
      "away_penalties": 2,
      "score_display": "3:3",
      "penalty_score": "4:2",
      "result_type": "penalties",
      "winner_team_id": "team_ARG",
      "text": "双方加时赛后战成3:3，阿根廷点球大战4:2获胜。",
      "source_ids": ["src_csv_20260716_001"]
    }
  ],
  "sources": [
    {
      "source_id": "src_csv_20260716_001",
      "title": "FIFA World Cup 1930-2022 All Match Dataset",
      "url": "https://www.kaggle.com/datasets/...",
      "source_type": "csv",
      "publisher": "Kaggle (Jahaidul Islam)",
      "retrieved_at": "2026-07-16",
      "data_version": "2026-07-16-v2",
      "used_for_fact_ids": ["fact-M-2022-64-result"]
    }
  ],
  "evidence": [
    {
      "chunk_id": "match_fact_M-2022-64_v2",
      "document_id": "match_fact_M-2022-64_v2",
      "match_id": "M-2022-64",
      "source_id": "src_csv_20260716_001",
      "document_name": "FIFA World Cup 2022",
      "source_url": "https://www.kaggle.com/datasets/...",
      "source_page": null,
      "text": "2022年世界杯决赛，阿根廷与法国在加时赛后3:3战平...",
      "language": "zh",
      "data_version": "2026-07-16-v2",
      "chunk_index": 0,
      "vector_distance": 0.17,
      "rerank_score": 0.96,
      "retrieval_rank": 3,
      "rerank_rank": 1
    }
  ],
  "confidence": null,
  "warnings": [],
  "timing": {
    "rewrite_ms": 30,
    "retrieval_ms": 60,
    "rerank_ms": 110,
    "generation_ms": 420,
    "total_ms": 620
  },
  "generation_meta": {
    "prompt_name": "summary",
    "prompt_version": "summary-v2.0",
    "model_name": "configured-model",
    "confidence_method": null
  }
}
```

## 3. 字段说明

### 3.1 顶层

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `answer` | string | ✅ | 最终自然语言答案 |
| `facts` | RAGFact[] | ✅ | 答案采用的结构化事实（用 fact_type 判别） |
| `sources` | SourceItem[] | ✅ | 去重后的实际使用来源 |
| `evidence` | EvidenceItem[] | ✅ | 进入生成上下文的检索证据（非全部候选） |
| `confidence` | number/null | ✅ | MVP 阶段固定 null |
| `warnings` | WarningItem[] | ✅ | 结构化告警 |
| `timing` | Timing | ✅ | 全链路耗时 |
| `generation_meta` | GenerationMeta | ✅ | Prompt、模型、置信度方法版本 |

### 3.2 RAGFact（可判别联合）

```text
MatchResultFact: 单场比分、阶段和胜负
  fact_type = "match_result"
  + match_id, score_display, penalty_score, result_type, winner_team_id
  + text, source_ids

RelationFact: 球队—对手关系
  fact_type = "relation"
  + team_ids, opponent_ids, match_ids
  + text, source_ids

SummaryFact: 多场/多届总结
  fact_type = "summary"
  + match_ids, tournament_years
  + text, source_ids
```

所有 Fact 必须包含：`fact_type`, `fact_id`, `text`, `source_ids`。

### 3.3 SourceItem

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `source_id` | string | ✅ | 来源唯一 ID |
| `title` | string | ✅ | 来源人类可读名称 |
| `url` | string | | 公开 URL |
| `source_type` | string | | csv / json / pdf / web |
| `publisher` | string | | 出版方 |
| `retrieved_at` | string | | 抓取日期 |
| `data_version` | string | | 数据版本 |
| `used_for_fact_ids` | string[] | | 该来源支撑了哪些事实 |

## 4. B 的组装

B 收到 RAGResult 后，组装统一前端响应：

```json
{
  "intent": "summary_query",
  "answer": "……",
  "facts": [],
  "sources": [],
  "graph": { "nodes": [], "edges": [] },
  "trace_id": "trace-20260716-001",
  "status": "ok",
  "warnings": []
}
```

- `answer`, `facts`, `sources`, `warnings` → 来自 E，不修改语义
- `intent`, `graph`, `trace_id` → B 自己生成
- `evidence` → 默认不发送前端，调试时通过参数控制

## 5. 告警代码

| code | 含义 |
|------|------|
| `NO_RESULT` | 无可靠事实或证据 |
| `OUT_OF_SCOPE` | 超出知识库范围 |
| `NEED_CLARIFICATION` | 条件不足 |
| `SOURCE_CONFLICT` | 结构化事实与文本证据不一致 |
| `LOW_CONFIDENCE` | 证据覆盖不足 |
| `QUERY_REWRITE_UNAVAILABLE` | Rewrite 未执行 |
| `RERANKER_UNAVAILABLE` | Reranker 未执行 |
| `RETRIEVAL_DEGRADED` | 检索降级 |
| `GENERATION_DEGRADED` | 生成降级 |

## 6. E 的确认清单

- [ ] E 不重新解析硬过滤条件，不直接读取底层数据库
- [ ] 事实融合以 B 的 StructuredFact 为准，语义补充来自 D 的 EvidenceItem
- [ ] 来源冲突时产生 SOURCE_CONFLICT 告警，不静默覆盖
- [ ] `evidence` 只包含实际进入上下文的条目（≤ rerank_top_n）
- [ ] 无可靠证据时不编造（status=empty）
- [ ] `confidence` MVP 阶段固定 null
- [ ] `generation_meta` 记录实际使用的 prompt 版本和模型名
