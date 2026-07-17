# D 成员：Chroma 与检索服务改进完善清单

## 1. 文档目的

本文用于明确 D 成员在世界杯知识库项目中的职责、当前 Chroma 方案的问题、整改优先级、交付物和验收标准。

D 的核心目标不是“写一份 `chroma_service_api.md`”，而是提供一套：

> 能实际运行、索引可重建、过滤条件可靠、结果可追溯、性能可测量、能够被 LangGraph 稳定调用的检索服务。

## 2. D 的职责边界

### D 必须负责

- Chroma collection 设计、创建、持久化和版本管理；
- Embedding 模型加载和批量向量化；
- 文档 ID、chunk ID、match ID 与 source ID 关联；
- Metadata Filter 的受控构造；
- Top-K 召回、去重、合并和评分；
- Query Rewrite 在语义/混合问题中的检索实现；
- Reranker 的加载、开关、降级和耗时记录；
- 索引重建、增量 upsert、删除和一致性校验；
- 检索单元测试与 Recall@K/MRR 等评测。

### D 不负责

- 原始比赛数据清洗和比分口径修复；
- FastAPI 对前端的 HTTP 接口；
- LangGraph 的总路由和意图识别；
- 最终答案 Prompt 和自然语言生成；
- D3.js 图数据组装；
- 通过 SQL 回答精确比分问题。

## 3. 当前设计的可用基础

`chroma_service_api.md` 已提出以下能力：

- `world_cup_match_facts` 和 `world_cup_reports` 两个 collection；
- `extract_filters()`；
- `query_top_k()`；
- 多查询召回、合并和去重；
- `query_with_rerank()`；
- 按 `match_id` 补充信息；
- 文档导入、删除和统计管理。

这些可以作为接口草案，但目前只有 Markdown 说明，尚不足以证明服务已经实现、能够运行或符合项目验收要求。

## 4. P0：必须立即完善的问题

### 4.1 交付实际可运行代码，而不只是接口说明

当前必须补交并验证：

- `backend/services/chroma_service.py` 或等价模块；
- collection 构建脚本；
- `requirements.txt` / `pyproject.toml` 中的固定版本；
- Embedding 模型配置；
- Chroma 持久化目录配置；
- 自动化测试；
- 索引统计和构建日志；
- 可复现的 README 命令。

验收不能只看函数签名，必须在新环境执行查询并得到稳定结果。

### 4.2 明确 SQL 与 Chroma 的分工

当前文档存在冲突：一处让“精确查询”调用 match facts collection，另一处又说明精确事实应直接查询 SQLite。

统一规则应为：

| 问题类型 | 首选方式 | Chroma 是否必需 |
|---|---|---:|
| 精确比分、日期、阶段、胜者 | SQLite | 否 |
| 比赛背景、过程总结、意义、评论 | reports collection | 是 |
| 事实条件下的总结 | SQL 筛选 + Chroma 报告检索 | 是 |
| 普通聊天 | 大模型 | 否 |

`world_cup_match_facts` 可以用于检索实验、模糊查找和兜底，但不应取代 SQL 成为精确事实的唯一来源。

### 4.3 补齐 world_cup_reports 数据

当前数据字典明确表示报告尚未导入。若 `world_cup_reports` 为 0，则系统不能真正回答“为什么、如何评价、比赛过程有什么特点”等语义问题。

最低要求：

- 推荐平衡版至少覆盖 2014、2018、2022 三届的代表性报告；
- 每场重点比赛至少有一份可引用的报告或官方页面；
- 每个 chunk 具有 `document_id`、`chunk_id`、`match_id`、`source_id`；
- 保存来源 URL、标题、抓取时间和许可说明；
- 对报告数量、chunk 数量和失败数生成导入报告。

如果暂时没有报告，必须在系统状态中明确：

```json
{
  "collection": "world_cup_reports",
  "status": "empty",
  "warnings": ["semantic report retrieval unavailable"]
}
```

不得把“只有结构化事实的向量搜索”宣传为完整比赛报告 RAG。

### 4.4 修改输入接口：接收结构化 RetrievalRequest

D 不应在每次调用时独立重新理解整句问题并覆盖 Agent 的判断。建议由 B/LangGraph 提供受控请求：

```json
{
  "query": "2022年世界杯决赛的重要情节",
  "collection": "world_cup_reports",
  "filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": ["penalties"],
    "match_ids": ["M-2022-64"]
  },
  "top_k": 10,
  "use_rewrite": true,
  "use_rerank": true
}
```

必须新增 `match_ids` 过滤，以支持真正的混合检索：

```text
SQL 先确定符合条件的比赛 ID
→ Chroma 只在这些 match ID 对应的报告中检索
```

### 4.5 返回结构化结果，不返回拼接字符串

`format_result()` 只能用于日志或调试，不能作为 B 的正式输入。正式返回建议为：

```json
{
  "items": [
    {
      "chunk_id": "chunk:report-001:03",
      "document_id": "report-001",
      "match_id": "M-2022-64",
      "source_id": "source-001",
      "text": "……",
      "distance": 0.18,
      "rerank_score": 0.86,
      "metadata": {}
    }
  ],
  "rewrite_applied": true,
  "queries": ["原始问题", "改写问题"],
  "rerank_applied": true,
  "warnings": [],
  "timing": {
    "embedding_ms": 40,
    "retrieve_ms": 25,
    "rerank_ms": 110
  },
  "index_version": "wc-reports-v2"
}
```

### 4.6 固定 Embedding 模型和 collection 版本

当前方案允许默认 Embedding 与 BGE 模型切换，但已建 collection 不能在查询时随意更换模型。

必须做到：

- 每个 collection 固定一个 embedding model；
- 保存模型名称、版本、向量维度、归一化方式和构建时间；
- 查询端必须使用与入库端相同的模型；
- 模型变化时建立新 collection 或完整重建；
- collection 名称或 manifest 中体现版本；
- 启动时检查维度和模型配置，不一致直接报错。

### 4.7 实现稳定的 ID 和幂等写入

建议 ID：

```text
比赛事实：match-fact:{match_id}:{data_version}
报告文档：report:{source_id}:{document_checksum}
报告分块：chunk:{document_id}:{chunk_index}
```

必须使用 upsert 或“先比对 checksum 再更新”的方式，避免重复运行导入脚本产生重复向量。

验收：连续执行两次导入后 collection 数量不增加。

## 5. P1：MVP 前建议完成的问题

### 5.1 Query Rewrite 只在需要时启用

不应默认对所有问题生成 2—3 个改写版本。

#### 建议开启

- 语义总结问题；
- 用户使用别名、简称或口语表达；
- 依赖上文的追问，需要转成独立问题；
- 首次召回分数较低或结果不足。

#### 建议关闭

- 精确比分、明确年份、明确双方球队；
- SQL 能直接回答的问题；
- 用户问题中的年份、球队、阶段属于硬约束时。

#### 强制要求

- 永远保留 `original_query`；
- 年份、team ID、stage、match ID 不允许由重写结果覆盖；
- 原始问题必须作为一个召回 query；
- 返回 `rewrite_applied` 和实际 query 列表；
- 为“2018 法国对阿根廷”建立约束保持测试。

### 5.2 Metadata Filter 必须受控生成

允许的字段白名单建议为：

- `year`；
- `stage`；
- `result_type`；
- `match_id`；
- `home_team_id`；
- `away_team_id`；
- `source_id`；
- `language`；
- `document_type`。

注意：Chroma metadata 对数组和复杂过滤的支持受版本限制。不要直接假设 `team_ids: [A, B]` 可以执行任意包含查询。更稳定的做法是保存：

```text
home_team_id = team_ARG
away_team_id = team_FRA
```

查询“任意一方为阿根廷”时，由服务构造受支持的 `$or` 条件。必须提供一个 filter builder，把结构化 filters 转换成当前 Chroma 版本支持的语法，不能让大模型直接输出 Chroma 查询表达式。

### 5.3 Reranker 必须有真实状态和降级信息

当前文档写了 `query_with_rerank()`，但 reranker 尚未部署。

最低实现建议：

```text
向量召回 Top-20
→ 去重
→ Reranker 重排
→ 返回 Top-5
```

返回必须包含：

- `rerank_requested`；
- `rerank_applied`；
- `reranker_model`；
- `fallback_reason`；
- `rerank_ms`。

模型不可用时可以退化为向量排序，但不得把降级后的结果伪装成已经重排。

### 5.4 修正相似度分数表达

不要直接把 `1 - distance` 当成准确率或置信概率。建议：

- 保留 Chroma 返回的原始 `distance`；
- 可提供统一的 `retrieval_score`，但明确计算方式；
- `confidence` 由上层综合判断，不能仅等于向量相似度；
- 阈值必须通过评测集确定，而不是凭经验写死。

### 5.5 解耦 Chroma 与 SQLite

当前 `enrich_result()` 计划直接根据 `match_id` 查询 SQLite，这会使 D 的模块同时承担检索和数据访问职责。

建议边界：

```text
D 返回 chunk_id、match_id、source_id 和检索分数
→ B 的 Evidence/Answer Service
→ 调用 C 提供的 Repository 补充比赛事实和来源
```

D 可以保留 `enrich_result()` 作为调试辅助函数，但正式 LangGraph 流程不应依赖它。

### 5.6 避免阻塞 FastAPI 事件循环

Chroma 查询、Embedding 和 Reranker 多为同步计算。D 应做到以下任一项：

- 提供 async 包装并在线程池执行同步调用；
- 或明确告知 B 必须通过 `run_in_threadpool` 调用；
- 模型只加载一次，不得每个请求重复加载；
- 记录并限制并发；
- 导入和批量 embedding 不在用户问答请求中执行。

### 5.7 区分“无结果”和“服务失败”

不能把所有异常捕获后都返回空列表。

建议状态：

- `ok`：查询成功且有结果；
- `empty`：查询成功但没有满足阈值的证据；
- `degraded`：reranker 等增强模块不可用，已降级；
- `unavailable`：collection、embedding 或 Chroma 不可用。

B 才能据此向前端正确显示“无可靠证据”或“检索服务暂时不可用”。

## 6. Collection 与文档设计建议

### 6.1 world_cup_match_facts

用途：

- 模糊事实检索；
- 球队别名和自然语言描述匹配；
- 检索实验和 SQL 兜底；
- 不作为精确比分的最高权威来源。

一场比赛生成一条完整事实，不能把球队、比分、阶段分别拆成不同 chunk。

### 6.2 world_cup_reports

用途：

- 比赛过程总结；
- 背景、意义和叙事性问题；
- SQL 过滤后的语义检索。

建议按语义段落或小节切分，而不是机械按字符截断。起始配置可使用约 400—800 中文字符、重叠 50—100 字，但最终应根据报告结构和检索实验调整。

每个 chunk 必须保留：

- `document_id`；
- `chunk_id`；
- `match_id`；
- `source_id`；
- `year`；
- `stage`；
- `home_team_id`；
- `away_team_id`；
- `language`；
- `data_version`；
- `checksum`。

## 7. 与 C、B、E 成员的接口

### 从 C 获取

- 已修正比分和日期的 `worldcup_v2.db`；
- `match_facts.jsonl`；
- 球队别名；
- source 清单；
- 稳定的 match ID、team ID、source ID；
- 数据版本、checksum、增量更新和删除清单。

在 C 修正比分之前，不应使用旧数据库重新生成最终 Chroma 索引，否则错误事实会被固化进向量库。

### 向 B（LangGraph/FastAPI）提供

- 一个稳定的 Python 检索接口；
- `RetrievalRequest` 和 `RetrievalResult` 数据结构；
- collection 状态查询；
- 结构化 warnings、timing、rewrite/rerank 状态；
- 明确异常类型；
- 调用示例和并发说明。

### 与 E（RAG/评测）协作

- 提供纯向量、Rewrite、Rerank、混合检索的开关；
- 输出 Top-K 文档 ID 和排序分数；
- 配合计算 Recall@K、MRR、nDCG@K；
- 固定索引版本和模型版本，保证消融实验可复现。

### D 不应做的事情

- 不应独立决定用户最终意图；
- 不应替代 SQL 查询精确事实；
- 不应返回最终自然语言答案；
- 不应直接返回 D3.js 节点和边；
- 不应让前端选择 collection、Top-K 或 reranker 模型。

## 8. D 应交付的文件

### P0 必须交付

1. 实际可运行的 Chroma service 源码；
2. `build_chroma_index.py` 或等价构建脚本；
3. collection manifest，记录模型、维度、版本、数量和 checksum；
4. `match_facts` 索引构建输入及统计；
5. `reports` 文档、chunk 清单及来源；
6. 固定依赖版本；
7. `.env.example` 中的模型和持久化配置；
8. `test_chroma_service.py`；
9. 构建日志和检索验证报告；
10. 更新后的内部接口文档。

### Git 管理要求

- Chroma 持久化目录默认不提交 Git；
- 本地模型权重不提交 Git；
- 提交构建脚本、manifest、小规模测试数据和下载说明；
- 路径必须从配置读取，不能写死成员电脑路径；
- 提供从空目录重建索引的命令。

## 9. 最低测试集

至少覆盖：

| 测试问题 | 预期行为 |
|---|---|
| 2022 年世界杯决赛比分 | 上层应走 SQL，D 不应强制介入 |
| 2022 年决赛有哪些重要情节 | reports 语义检索 |
| 阿根廷在 2022 淘汰赛中的表现 | 年份、球队、阶段过滤 + 语义检索 |
| 2018 法国对阿根廷 | 保留年份和球队硬约束 |
| Germany / 德国 / 德国队 | 归一到同一 team ID |
| 近三届世界杯决赛有什么共同点 | 多年份过滤 + 多文档召回 |
| 某个不存在的球队 | 返回 empty 或规范化失败，不得伪造 |
| reports collection 不可用 | 返回 unavailable/degraded，而不是普通空结果 |
| reranker 模型未加载 | 正确降级并返回 fallback_reason |
| 连续导入两次 | collection 数量不重复增长 |

## 10. 最低评测要求

建议准备至少 30—50 个检索问题，每个问题标注相关文档或 match ID，完成：

1. 基础向量检索；
2. 向量检索 + Metadata Filter；
3. 向量检索 + Query Rewrite；
4. 向量检索 + Reranker；
5. SQL 过滤 match ID + Chroma 的混合检索。

至少记录：

- Recall@5、Recall@10；
- MRR；
- nDCG@5；
- Top-3 相关率；
- 平均检索时间；
- Rewrite 增益和改错条件次数；
- Reranker 增益及延迟。

## 11. 最终验收清单

- [ ] Chroma service 有实际源码并能在新环境运行；
- [ ] collection 可由脚本从空目录重建；
- [ ] ingestion 和 query 使用完全相同的 embedding 模型；
- [ ] collection manifest 记录模型、维度和索引版本；
- [ ] 连续导入不会产生重复向量；
- [ ] `match_id`、`source_id` 能追溯到 C 的数据库；
- [ ] 支持 `match_ids` 过滤以完成真正混合检索；
- [ ] Query Rewrite 不改变年份、球队和阶段硬条件；
- [ ] Metadata Filter 只由受控 builder 生成；
- [ ] Reranker 的真实启用和降级状态可见；
- [ ] 返回结构化结果、warnings 和 timing；
- [ ] 能区分 empty、degraded 和 unavailable；
- [ ] reports collection 非空，或系统明确声明语义检索不可用；
- [ ] 检索有测试集和基础指标；
- [ ] Chroma 持久化目录和模型文件未直接提交 Git。

## 12. D 的完成定义

D 的工作完成，不是“Chroma 中能搜出几段文字”，而是：

> LangGraph 能传入明确的查询和过滤条件，D 能稳定返回可追溯、可解释、可降级的候选证据；索引能够在新环境重建，并能通过实验说明 Rewrite、Filter 和 Reranker 是否真正有效。

