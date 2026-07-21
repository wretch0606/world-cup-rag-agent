# RAG 模块输入输出接口契约 v1.1（建议版）

## 0. 文档状态

| 项目 | 内容 |
|---|---|
| 契约版本 | `rag-v1.1-draft` |
| 当前状态 | B、D、E 联调评审稿，确认后冻结 |
| 适用范围 | FastAPI/LangGraph（B）、Chroma 检索（D）、RAG 生成与评测（E） |
| 核心原则 | 精确事实走 SQLite；语义与混合问题调用 RAG；所有结论可追溯到 `source_id` |

字段冻结后，应在共享代码目录中建立统一 Pydantic 模型。任何字段变更必须同步修改契约版本、模型、测试用例和前端映射。

---

## 1. 已确定的模块边界

### 1.1 精确事实问题

`exact_fact` 包括比分、日期、阶段、胜者、比赛列表等可直接由 SQLite 返回的问题。

```text
FastAPI → LangGraph 路由 → SQLite Service → B 确定性格式化 → 前端统一响应
```

精确事实问题默认不调用 Chroma 和大模型，避免事实误写并降低延迟。E 可以评测该链路，但不负责其运行时答案生成。

### 1.2 语义和混合问题

```text
FastAPI 接收请求
→ B 完成路由、实体识别、别名归一和 SQL 预查询
→ E 接收 RAGRequest
→ E 调用 D 的 Retrieval Service
→ D 执行 Query Rewrite、Chroma 召回和 Reranker
→ E 融合 StructuredFact、EvidenceItem 和来源信息
→ E 生成 RAGResult
→ B 组装前端统一响应
```

### 1.3 责任原则

- B 不从全部 evidence 中猜测答案实际使用了哪些来源。
- D 不生成最终自然语言答案。
- E 不直接读取数据库底层字段，也不重复实现 Chroma 检索、Rewrite 或 Reranker。
- 前端的 `graph`、筛选器、比赛列表和时间线由 B/A 负责，不由 E 生成。

---

## 2. 通用约定

### 2.1 标识符

- `trace_id`：单次请求链路标识，由 B 生成，全链路透传。
- `match_id`、`team_id`、`source_id`、`document_id`、`chunk_id`：必须与 C、D 的实际数据一致。
- 重复导入不得产生不同语义的同一 ID。

### 2.2 枚举与显示名称

后端契约统一使用英文枚举，中文名称使用独立的 `*_name` 字段。

```text
stage: group, second_group, round_of_16, quarter_final, semi_final, third_place, final_round, final
result_type: regulation, draw, extra_time, penalties
query_type: semantic, hybrid
```

禁止同一字段同时出现 `final`、`决赛`、`Final` 等多种取值。

### 2.3 空值

- 数组没有数据时返回 `[]`，不返回 `null`。
- 可选标量没有数据时返回 `null`。
- 空数组过滤条件表示“不应用该条件”。
- `0` 不能用来表示“未知”。

### 2.4 分数方向

- `vector_distance`：越小越相关；没有返回时为 `null`。
- `rerank_score`：越大越相关；未启用或无法计算时为 `null`。
- D 必须同时返回排序后的 `retrieval_rank` 和 `rerank_rank`，便于实验复现。

### 2.5 时间

所有耗时字段统一使用毫秒，字段以 `_ms` 结尾。

---

## 3. B → E：RAGRequest

### 3.1 完整示例

```json
{
  "contract_version": "rag-v1.1-draft",
  "trace_id": "trace-20260716-001",
  "question": "2022年世界杯决赛有哪些重要情节？",
  "original_question": "介绍一下2022年世界杯决赛",
  "query_type": "hybrid",
  "filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": [],
    "match_ids": ["M-2022-64"]
  },
  "structured_facts": [
    {
      "match_id": "M-2022-64",
      "match_date": "2022-12-18",
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
      "source_ids": ["source-001"]
    }
  ],
  "source_catalog": [
    {
      "source_id": "source-001",
      "title": "FIFA World Cup 2022",
      "url": "https://example.org/world-cup-2022-final",
      "page": null,
      "document_id": "document-001",
      "data_version": "2026-07-16-v1"
    }
  ],
  "options": {
    "retrieval_top_k": 10,
    "rerank_top_n": 5,
    "use_query_rewrite": true,
    "use_reranker": true,
    "min_rerank_score": null,
    "timeout_ms": 8000
  }
}
```

### 3.2 RAGRequest 字段

| 字段 | 类型 | 必填 | 提供方 | 说明 |
|---|---|---:|---|---|
| `contract_version` | string | 是 | B | 当前契约版本 |
| `trace_id` | string | 是 | B | 请求跟踪 ID |
| `question` | string | 是 | B | 已补全上下文、可独立理解的问题 |
| `original_question` | string | 是 | B | 用户原始问题，保护硬约束不被 Rewrite 改写 |
| `query_type` | enum | 是 | B | `semantic` 或 `hybrid` |
| `filters` | RetrievalFilters | 是 | B | 已归一和校验的硬过滤条件 |
| `structured_facts` | StructuredFact[] | 是 | B/SQL Service | `hybrid` 必须提供；`semantic` 可为空 |
| `source_catalog` | SourceItem[] | 是 | B/SQL Service | 结构化事实对应的来源信息 |
| `options` | RAGOptions | 是 | B/E 配置 | 检索、重排和超时配置 |

### 3.3 RetrievalFilters

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `years` | integer[] | `[]` | 世界杯年份 |
| `team_ids` | string[] | `[]` | 规范球队 ID |
| `stages` | StageEnum[] | `[]` | 统一阶段枚举 |
| `result_types` | ResultTypeEnum[] | `[]` | 结果类型 |
| `match_ids` | string[] | `[]` | SQL 预筛选的比赛 ID |

Query Rewrite 不得修改、删除或新增与以下硬约束冲突的条件：年份、球队 ID、阶段、结果类型和比赛 ID。

### 3.4 StructuredFact

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `match_id` | string | 是 | 比赛 ID |
| `match_date` | date/null | 否 | 比赛日期 |
| `tournament_year` | integer | 是 | 世界杯年份 |
| `stage` | StageEnum | 是 | 后端枚举 |
| `stage_name` | string | 是 | 中文显示名称 |
| `home_team_id/name` | string | 是 | 主队 ID 与显示名称 |
| `away_team_id/name` | string | 是 | 客队 ID 与显示名称 |
| `home_score_90`、`away_score_90` | integer/null | 否 | 90 分钟比分 |
| `home_score_et`、`away_score_et` | integer/null | 否 | 加时结束后的累计比分 |
| `home_penalties`、`away_penalties` | integer/null | 否 | 点球大战比分 |
| `score_display` | string | 是 | 对用户展示的正式比分 |
| `penalty_score` | string/null | 否 | 点球比分，必须与正式比分分开 |
| `result_type` | ResultTypeEnum | 是 | 决胜方式 |
| `winner_team_id` | string/null | 否 | 平局时为 `null` |
| `source_ids` | string[] | 是 | 事实来源 |

E 不得根据 ID 猜测球队中文名，不得自行从底层数据库字段推导未确认的比分口径。

### 3.5 RAGOptions

| 字段 | 类型 | 默认值 | 限制 |
|---|---|---:|---|
| `retrieval_top_k` | integer | 10 | 1—50，初始向量召回数 |
| `rerank_top_n` | integer | 5 | 1—`retrieval_top_k`，重排后保留数 |
| `use_query_rewrite` | boolean | false | 是否允许 D 执行 Rewrite |
| `use_reranker` | boolean | false | 是否允许 D 执行 Reranker |
| `min_rerank_score` | number/null | null | 可选最低分阈值，使用前必须确定模型分数范围 |
| `timeout_ms` | integer | 8000 | 建议 1000—30000 |

---

## 4. E → D：RetrievalRequest

E 将 B 提供的硬约束原样传给 D，不重新解析球队、年份或阶段。

```json
{
  "contract_version": "rag-v1.1-draft",
  "trace_id": "trace-20260716-001",
  "query": "2022年世界杯决赛有哪些重要情节？",
  "original_question": "介绍一下2022年世界杯决赛",
  "filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": [],
    "match_ids": ["M-2022-64"]
  },
  "options": {
    "retrieval_top_k": 10,
    "rerank_top_n": 5,
    "use_query_rewrite": true,
    "use_reranker": true,
    "min_rerank_score": null,
    "timeout_ms": 8000
  }
}
```

---

## 5. D → E：RetrievalResult

### 5.1 完整示例

```json
{
  "contract_version": "rag-v1.1-draft",
  "trace_id": "trace-20260716-001",
  "status": "ok",
  "original_query": "2022年世界杯决赛有哪些重要情节？",
  "rewritten_queries": [
    "2022 世界杯 决赛 阿根廷 法国 比赛过程 关键事件"
  ],
  "items": [
    {
      "chunk_id": "chunk-001",
      "document_id": "document-001",
      "collection": "world_cup_reports",
      "match_id": "M-2022-64",
      "source_id": "source-001",
      "document_name": "FIFA World Cup 2022",
      "source_url": "https://example.org/world-cup-2022-final",
      "source_page": null,
      "text": "阿根廷与法国在决赛中多次交换领先优势……",
      "language": "zh",
      "data_version": "2026-07-16-v1",
      "chunk_index": 12,
      "vector_distance": 0.18,
      "rerank_score": 0.86,
      "retrieval_rank": 3,
      "rerank_rank": 1
    }
  ],
  "applied_filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": [],
    "match_ids": ["M-2022-64"]
  },
  "rewrite_applied": true,
  "rerank_applied": true,
  "warnings": [],
  "timing": {
    "rewrite_ms": 30,
    "retrieval_ms": 60,
    "rerank_ms": 110,
    "total_ms": 200
  },
  "error": null
}
```

### 5.2 EvidenceItem 必要字段

| 字段组 | 字段 |
|---|---|
| 定位 | `chunk_id`、`document_id`、`collection`、`match_id` |
| 来源 | `source_id`、`document_name`、`source_url`、`source_page` |
| 内容 | `text`、`language`、`data_version`、`chunk_index` |
| 评分 | `vector_distance`、`rerank_score`、`retrieval_rank`、`rerank_rank` |

`source_url` 和 `source_page` 允许为 `null`，但 `source_id`、`document_name` 和 `data_version` 必须存在。

### 5.3 D 的执行责任

- D 内部执行 Query Rewrite、Chroma 过滤召回和 Reranker。
- E 通过 `options` 控制是否开启，不重复实现算法。
- D 必须返回实际执行状态，不能只回显请求开关。
- Rewrite 失败但原查询仍可检索时返回 `degraded`，继续召回。
- Reranker 失败但向量结果可用时返回 `degraded`，使用原始排序。

---

## 6. E → B：RAGResult

### 6.1 完整示例

```json
{
  "contract_version": "rag-v1.1-draft",
  "trace_id": "trace-20260716-001",
  "status": "ok",
  "answer": "阿根廷与法国在90分钟内战成2:2，加时赛结束后为3:3；阿根廷最终在点球大战中以4:2获胜。比赛过程中双方多次交换领先优势。",
  "facts": [
    {
      "fact_type": "match_result",
      "fact_id": "fact-M-2022-64-result",
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
      "source_ids": ["source-001"]
    }
  ],
  "sources": [
    {
      "source_id": "source-001",
      "title": "FIFA World Cup 2022",
      "url": "https://example.org/world-cup-2022-final",
      "page": null,
      "document_id": "document-001",
      "data_version": "2026-07-16-v1",
      "used_for_fact_ids": ["fact-M-2022-64-result"]
    }
  ],
  "evidence": [
    {
      "chunk_id": "chunk-001",
      "document_id": "document-001",
      "collection": "world_cup_reports",
      "match_id": "M-2022-64",
      "source_id": "source-001",
      "document_name": "FIFA World Cup 2022",
      "source_url": "https://example.org/world-cup-2022-final",
      "source_page": null,
      "text": "阿根廷与法国在决赛中多次交换领先优势……",
      "language": "zh",
      "data_version": "2026-07-16-v1",
      "chunk_index": 12,
      "vector_distance": 0.18,
      "rerank_score": 0.86,
      "retrieval_rank": 3,
      "rerank_rank": 1
    }
  ],
  "applied_filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": [],
    "match_ids": ["M-2022-64"]
  },
  "confidence": null,
  "rewrite_applied": true,
  "rerank_applied": true,
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
    "prompt_version": "summary-v1.0",
    "model_name": "configured-model",
    "confidence_method": null
  },
  "error": null
}
```

### 6.2 RAGResult 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `contract_version` | string | 是 | 契约版本 |
| `trace_id` | string | 是 | 与请求一致 |
| `status` | RAGStatus | 是 | `ok`、`empty`、`degraded`、`error` |
| `answer` | string | 是 | 对用户的最终回答；无结果时为规范限制说明 |
| `facts` | RAGFact[] | 是 | 答案实际采用的结构化事实 |
| `sources` | SourceItem[] | 是 | 答案实际采用并去重后的来源 |
| `evidence` | EvidenceItem[] | 是 | 进入生成上下文的证据，不是 D 返回的全部候选 |
| `applied_filters` | RetrievalFilters | 是 | 实际生效的过滤条件 |
| `confidence` | number/null | 是 | 未建立校准方法前固定返回 `null` |
| `rewrite_applied` | boolean | 是 | 实际执行状态 |
| `rerank_applied` | boolean | 是 | 实际执行状态 |
| `warnings` | WarningItem[] | 是 | 结构化告警 |
| `timing` | RAGTiming | 是 | 全链路耗时 |
| `generation_meta` | GenerationMeta | 是 | Prompt、模型和置信度方法版本 |
| `error` | ErrorItem/null | 是 | 非错误状态为 `null` |

### 6.3 Facts 设计

`facts` 使用 `fact_type` 作为判别字段，Pydantic 应实现为可判别联合类型：

```text
MatchResultFact: 单场比分、阶段和胜负
RelationFact: 球队—对手关系及对应比赛
SummaryFact: 多场或多届总结所采用的 match_ids 与陈述
```

所有 Fact 必须至少包含：`fact_type`、`fact_id`、`text`、`source_ids`。涉及具体比赛时必须包含 `match_id`。

### 6.4 Sources 设计

- `sources` 只包含最终答案真正使用的来源，不返回全部候选来源。
- 同一 `source_id` 只出现一次。
- `used_for_fact_ids` 用于说明来源支持哪些事实。
- B 将该数组直接映射到前端统一响应，不重新推断来源。

---

## 7. WarningItem

### 7.1 结构

```json
{
  "code": "SOURCE_CONFLICT",
  "message": "结构化比分与文本证据不一致，已保留结构化事实并提示复核。",
  "component": "fact_fusion",
  "retryable": false
}
```

### 7.2 告警代码

| code | 含义 |
|---|---|
| `NO_RESULT` | 没有可靠事实或证据 |
| `OUT_OF_SCOPE` | 超出知识库范围 |
| `NEED_CLARIFICATION` | 条件不足，需要澄清 |
| `SOURCE_CONFLICT` | 事实或来源冲突 |
| `LOW_CONFIDENCE` | 证据覆盖不足 |
| `QUERY_REWRITE_UNAVAILABLE` | Rewrite 未能执行 |
| `RERANKER_UNAVAILABLE` | Reranker 未能执行 |
| `RETRIEVAL_DEGRADED` | 检索使用降级方案 |
| `GENERATION_DEGRADED` | 生成阶段使用降级方案 |
| `TIMEOUT_PARTIAL` | 超时但存在可返回的部分结果 |

`component` 使用：`routing`、`sql`、`retrieval`、`reranker`、`fact_fusion`、`generation`。

---

## 8. 状态与错误

### 8.1 RAGStatus

| status | 条件 | answer | error |
|---|---|---|---|
| `ok` | 正常完成且证据可靠 | 正常答案 | `null` |
| `empty` | 查询成功但无可靠结果 | 规范的无结果说明 | `null` |
| `degraded` | 增强模块失败但核心流程可用 | 有限答案并披露告警 | `null` |
| `error` | 无法产生安全结果 | 简短失败说明 | ErrorItem |

### 8.2 ErrorItem

```json
{
  "code": "RETRIEVAL_ERROR",
  "message": "知识库检索暂时不可用。",
  "component": "retrieval",
  "retryable": true,
  "detail_id": "error-trace-20260716-001"
}
```

允许的错误代码：

```text
VALIDATION_ERROR
RETRIEVAL_ERROR
GENERATION_ERROR
TIMEOUT
INTERNAL_ERROR
```

`message` 不得包含 API Key、数据库连接串、内部堆栈或服务器绝对路径；详细错误写入日志，通过 `detail_id` 查询。

---

## 9. Confidence 规则

- MVP 阶段 `confidence` 固定返回 `null`。
- 禁止直接采用大模型自报置信度。
- 禁止把单一向量相似度直接作为最终置信度。
- 只有建立可复现的校准公式，并在测试集上验证后才能返回 0—1 数值。
- 启用后必须在 `generation_meta.confidence_method` 中记录算法版本。

建议未来综合以下因素：结构化事实覆盖率、必要来源覆盖率、Reranker 分数、来源冲突状态和问题类型。

---

## 10. B 的前端统一响应映射

B 收到 RAGResult 后组装：

```json
{
  "intent": "summary_query",
  "answer": "……",
  "facts": [],
  "sources": [],
  "graph": {
    "nodes": [],
    "edges": []
  },
  "trace_id": "trace-20260716-001",
  "status": "ok",
  "warnings": []
}
```

映射要求：

- `answer`、`facts`、`sources`、`warnings` 不修改语义，直接来自 E。
- `intent`、`graph`、`trace_id` 和 HTTP 状态由 B 负责。
- `evidence` 默认不全部发送前端；需要调试展示时由接口参数控制。
- `status=error` 时由 B 映射为统一业务错误，HTTP 状态码由 B 的 API 规范决定。

---

## 11. Pydantic 冻结要求

至少建立以下共享模型：

```text
RAGRequest
RetrievalFilters
StructuredFact
SourceItem
RAGOptions
RetrievalRequest
RetrievalResult
EvidenceItem
RAGResult
MatchResultFact
RelationFact
SummaryFact
WarningItem
ErrorItem
RetrievalTiming
RAGTiming
GenerationMeta
```

模型约束：

- 核心字段禁止使用无约束 `dict`。
- 枚举使用 `Enum` 或 `Literal`。
- 所有模型建议设置 `extra="forbid"`，避免拼错字段后静默通过。
- 所有数组使用 `default_factory=list`。
- `retrieval_top_k`、`rerank_top_n`、`timeout_ms` 设置范围校验。
- 校验 `rerank_top_n <= retrieval_top_k`。
- `confidence` 非空时限制在 0—1。
- `status != error` 时 `error` 必须为 `null`；`status=error` 时 `error` 必须存在。
- `result_type=penalties` 时必须存在 `penalty_score`。
- `result_type=draw` 时 `winner_team_id` 必须为 `null`。
- `trace_id` 和 `contract_version` 在各层返回中必须保持一致。

共享模型建议放置在：

```text
backend/schemas/rag_contract.py
```

B、D、E 必须从同一文件导入模型，禁止各自复制一份。

### 11.1 子契约说明

`docs/03-E-to-B-RAG生成结果接口契约.md`（`generation-v2.0`）是 E→B 生成数据子契约，不定义独立的 `contract_version`。其 SourceItem 扩展字段（`source_type`、`publisher`、`retrieved_at`）已吸收到本契约的 SourceItem 模型中。完整 RAGResult 的链路控制字段（`contract_version`、`trace_id`、`status`、`applied_filters`、`error`）由本契约统一定义。

### 11.2 运行时入口

B 通过进程内异步 Python 调用 `RagService.generate(request: RAGRequest) -> RAGResult`，不引入内部 HTTP 接口。`RagService` 通过 `RetrievalGateway` Protocol 调用 D，B 不直接依赖 D 的实现。入口代码位于：

```text
backend/rag/service.py      — RagService 类
backend/rag/protocols.py    — RetrievalGateway / GenerationClient 协议
```

---

## 12. 联调验收用例

### 12.1 正常语义问题

- D 返回至少一条可追溯 EvidenceItem。
- E 返回非空答案、去重后的 sources 和 timing。
- 进入生成上下文的 evidence 数量不超过 `rerank_top_n`。

### 12.2 混合问题

- B 先通过 SQL 返回 StructuredFact 和 match_ids。
- D 只在 match_ids 范围内检索。
- 比分与胜负来自 StructuredFact；解释和背景来自 EvidenceItem。

### 12.3 点球问题

- `score_display` 与 `penalty_score` 分开。
- 答案采用“加时赛后 X:Y；点球大战 P:Q”的表达。
- 不得将点球比分计入正式比赛进球。

### 12.4 无结果

- `status=empty`。
- `facts=[]`、`sources=[]`、`evidence=[]`。
- `warnings` 包含 `NO_RESULT`。
- 不生成具体比分、日期或胜者。

### 12.5 来源冲突

- `status=degraded`。
- `warnings` 包含 `SOURCE_CONFLICT`。
- 答案说明存在冲突并提示复核，不能静默选择文本证据。

### 12.6 Rewrite 降级

- `status=degraded`。
- `rewrite_applied=false`。
- 使用原问题继续检索。
- 告警包含 `QUERY_REWRITE_UNAVAILABLE`。

### 12.7 Reranker 降级

- `status=degraded`。
- `rerank_applied=false`。
- 使用向量召回原始排序。
- 告警包含 `RERANKER_UNAVAILABLE`。

### 12.8 超时与服务错误

- 有安全的部分结果时可以返回 `degraded` + `TIMEOUT_PARTIAL`。
- 无法产生安全结果时返回 `error` + ErrorItem。
- 返回内容不得泄露内部异常堆栈。

---

## 13. B、D、E 冻结确认清单

### B 确认

- [ ] `exact_fact` 由 B 通过 SQLite 直接处理。
- [ ] B 提供归一后的 filters、StructuredFact 和 source_catalog。
- [ ] B 直接使用 E 返回的 answer、facts、sources 和 warnings。
- [ ] 图数据与最终 HTTP 响应由 B 负责。

### D 确认

- [ ] D 支持 years、team_ids、stages、result_types 和 match_ids 过滤。
- [ ] D 内部负责 Rewrite、Chroma 召回和 Reranker。
- [ ] EvidenceItem 包含来源、版本、评分和排序字段。
- [ ] D 明确 vector_distance 与 rerank_score 的方向和空值规则。

### E 确认

- [ ] E 不重新解析硬过滤条件，不直接读取底层数据库。
- [ ] E 负责事实融合、最终答案、sources、warnings 和 generation_meta。
- [ ] E 只把实际进入上下文的 evidence 放入 RAGResult。
- [ ] E 在无可靠证据时不编造，在冲突时明确提示。

### 共同确认

- [ ] 契约版本、枚举和 Pydantic 模型路径已冻结。
- [ ] 30 道初始测试题中的事实和来源已经 C 复核。
- [ ] B、D、E 均通过正常、无结果、降级、冲突和错误联调用例。
- [ ] 字段变更流程和负责人已经确定。

---

## 14. 当前推荐结论

> B 负责路由、SQL 精确事实、过滤条件和前端统一响应；D 负责 Query Rewrite、Chroma 过滤召回和 Reranker；E 负责融合结构化事实与检索证据，生成答案、事实、最终来源和结构化告警。精确事实问题由 B 直接处理，不经过 E 的生成链路。MVP 阶段不输出未经校准的 confidence 数值。
