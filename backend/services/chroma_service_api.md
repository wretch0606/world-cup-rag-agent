# Chroma 向量数据库模块 — 接口文档（成员 D → E / B）

> **版本**：v1.2（适配 C 的 v2.1 契约 + 对齐 B_C_D 协调清单）
> **日期**：2026-07-19
> **维护者**：成员 D
> **模块路径**：`backend/services/chroma_service.py`
> **调用链**：B → E → D（B 不直接调 D，E 是中间层）

---

## 一、模块概述

本模块封装世界杯知识库的全部 Chroma 向量数据库操作。E（RAG 生成）通过 `query_structured()` 获得结构化检索结果，B（Agent）不直接调用 D。

### 1.1 架构位置

```
用户 → B (LangGraph Agent)
         │
         ├─ 结构化查询 → SQLite (worldcup_v2.db)   ← B 自己查
         │
         └─ 语义检索   → E (RAG Service)
                           │
                           └─ D: query_structured()  ← E 调用 D
                                ├─ extract_filters()  → 提取过滤条件
                                ├─ query_top_k()      → Chroma 语义检索
                                └─ RetrievalResponse  → 结构化结果
```

### 1.2 Collection

| Collection | 数据 | 用途 |
|-----------|------|------|
| `world_cup_match_facts` | 964 条，v2.1 英文 stage enum | 比赛事实语义检索 |
| `world_cup_reports` | 0 条（待 C 提供） | 比赛报告/长篇分析 |

---

## 二、快速开始

```python
from backend.services.chroma_service import (
    query_structured,      # 推荐：E 调用的主接口
    query_top_k,           # 备选：原始检索
    enrich_result,         # 可选：调试增强（查 SQLite）
    COLLECTION_FACTS,
)

# ── E 的调用示例 ──
response = query_structured(
    query_text="2022年世界杯决赛比分",
    k=5,
    collection=COLLECTION_FACTS,
    use_rewrite=True,
    use_rerank=False,
)

# response.to_dict() → {"status": "ok", "candidates": [...], "execution": {...}}
```

---

## 三、核心 API

### 3.1 `query_structured()` — 推荐 E 使用

```python
response = query_structured(
    query_text: str,
    k: int = 5,
    collection: str = COLLECTION_FACTS,
    filters: dict | None = None,
    use_rewrite: bool = True,
    use_rerank: bool = False,
    recall_k: int = 20,
) -> RetrievalResponse
```

返回 `RetrievalResponse` 对象（对齐 02-D-to-E 契约 v2.0），调用 `.to_dict()` 得到：

```json
{
  "query": "2022年世界杯决赛",
  "status": "ok",
  "rewritten_query": "2022 世界杯 决赛",
  "filters": {"tournament_year": 2022, "stage": "final"},
  "config": {"top_k": 5, "reranker_enabled": false, "use_rewrite": true},
  "candidates": [
    {
      "text": "2022年世界杯决赛...",
      "vector_score": 0.18,
      "rerank_score": null,
      "retrieval_rank": 1,
      "rerank_rank": null,
      "metadata": {
        "match_id": "M-2022-64",
        "stage": "final",
        "stage_name": "决赛",
        "source_ids": ["src_csv_20260719_001", "source-kaggle-001"],
        "data_version": "2026-07-16-v2"
      }
    }
  ],
  "execution": {
    "rewrite_applied": true,
    "reranker_applied": false,
    "warnings": [],
    "timing": {"retrieval_ms": 30}
  }
}
```

**status 取值**：

| status | 含义 |
|--------|------|
| `ok` | 查询成功且有结果 |
| `empty` | 查询成功但无满足阈值的证据 |
| `degraded` | reranker 等增强不可用，已降级 |
| `error` | collection 为空或不可用 |

### 3.2 `query_top_k()` — 原始检索

```python
results = query_top_k(
    query_text: str,
    k: int = 5,
    collection: str = COLLECTION_FACTS,
    filters: dict | None = None,
    use_query_rewrite: bool = True,
) -> list[dict]
```

返回 Chroma 原始格式（见 3.1 的 `candidates` 项）。

**内部流程**：query expansion（多角度改写）→ Chroma 检索（metadata 过滤）→ 去重 → 按相似度排序。

### 3.3 `extract_filters()` — 查询预处理

```python
filters = extract_filters("2018年法国队在决赛的表现")
# → {
#     "tournament_year": 2018,
#     "team": "法国",
#     "team_id": "team_FRA",
#     "stage": "final",                 # ← 英文 enum（数据 v2.1）
#     "stage_name": "决赛",              # ← 中文显示名
#     "rewritten_query": "法国队表现",
# }
```

**v2.1 变更**：`stage` 字段返回英文 enum（如 `"final"`、`"semi_final"`），直接用于 Chroma where 过滤。`stage_name` 保留中文供前端展示。

**支持中英文输入**：用户输入 "semi-finals" 或 "半决赛" 都能识别 → `semi_final`。

### 3.4 `enrich_result()` — 调试增强（可选）

⚠️ **仅用于调试和日志**。正式 RAG 流程中，B/E 应通过 SQLite 自行补充比赛详情。

```python
enriched = enrich_result(item)
# 在原始 metadata 基础上增加:
#   team_names: ["法国", "克罗地亚"]
#   match_detail: {score_display, venue, match_date, ...}
#   goals: [{player, minute_label, penalty, ...}, ...]
```

### 3.5 `get_goal_details()` — 进球查询

```python
goals = get_goal_details("M-2022-64")
# → [{"player": "Lionel Messi", "minute_label": "23'", "penalty": 1, ...}, ...]
```

---

## 四、管理 API

### 4.1 `import_match_facts()` — 数据导入

```python
count = import_match_facts("D/match_facts.jsonl")  # 自动检测 .json 和 .jsonl
# → 964 条 upsert 完成
```

**幂等**：使用 Chroma upsert，两次导入 count 不增加。

### 4.2 `add_chunks()` / `list_documents()` / `delete_document()` / `get_collection_stats()`

标准 CRUD，详见函数签名。

---

## 五、v2.1 契约关键变更

| 字段 | v2.0（旧） | v2.1（新） |
|------|-----------|-----------|
| 阶段 | `stage: "决赛"`（中文） | `stage: "final"`（英文 enum） |
| 阶段中文 | 无 | `stage_name: "决赛"`（新增） |
| 来源 | `source_id: "..."`（单值） | `source_ids: ["...", "..."]`（数组） |
| 数据版本 | `"1.0"` | `"2026-07-16-v2"` |
| 阶段枚举 | 无标准 | 8 个英文 enum（见 D/stage_mapping.json） |

**8 个 stage enum**：`group`, `second_group`, `round_of_16`, `quarter_final`, `semi_final`, `third_place`, `final`, `final_round`

---

## 六、数据文件依赖

| 文件 | 位置 | 用途 |
|------|------|------|
| `match_facts.jsonl` | `D/` | 964 条事实文本，导入 Chroma |
| `team_aliases.json` | `D/` | 255 条球队别名（query rewrite 用） |
| `stage_mapping.json` | `D/` | stage 英文 enum ↔ 中文显示名 |
| `source_manifest.json` | `D/` | 数据来源清单 |
| `worldcup_v2.db` | 项目根目录 | SQLite（`enrich_result` 调试增强用） |

**代码自动搜索路径**（优先级）：环境变量 > D/ 文件夹 > 项目根 > 交付/ 目录。

---

## 七、环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_MODE` | `default` | `default`（Chroma 内置）/ `bge`（中文精准） |
| `CHROMA_DATA_DIR` | `./backend/data/chroma_db` | Chroma 持久化目录 |
| `TEAM_ALIASES_PATH` | 自动搜索 `D/team_aliases.json` | 球队别名文件 |
| `WORLD_CUP_DB_PATH` | 自动搜索 `worldcup_v2.db` | SQLite 数据库路径 |

---

## 八、错误处理

| 场景 | 行为 |
|------|------|
| 参数错误（空 query、k 越界） | 抛出 `ValueError` |
| 无检索结果 | `query_structured()` 返回 `status="empty"` |
| collection 为空 | `query_structured()` 返回 `status="error"` |
| reranker 不可用 | 返回 `status="degraded"`，自动降级为向量排序 |
| 文件找不到 | 通过 logger 输出 warning，降级运行（返回空结果） |

---

## 九、与 B、C 的分工

| 事项 | 谁负责 |
|------|--------|
| Chroma 语义检索 | D（本模块） |
| 结构化 SQL 精确查询 | B（直接查 worldcup_v2.db） |
| Agent 路由 / 意图识别 | B |
| RAG Prompt / LLM 调用 | E |
| 数据清洗、交付 | C |
| 检索结果增强（比分/进球） | B/E 通过 SQLite 自行补充，`enrich_result()` 仅调试用 |

---

## 十、性能参考

| 指标 | 值 |
|------|-----|
| Chroma 数据量 | 964 chunks，512 维（BGE） |
| 单次检索延迟（BGE） | ~30ms |
| 含 query expansion | ~100ms |
| 首次加载 BGE 模型 | ~10s（后续缓存） |
| 幂等导入 | upsert，重复执行 964→964 不变 |

---

> **有任何问题找 D 联调。**
