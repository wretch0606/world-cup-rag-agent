# Chroma 向量数据库模块 — 接口文档（成员 D → 成员 B）

> **版本**：v1.0  
> **维护者**：成员 D  
> **模块路径**：`backend/services/chroma_service.py`

---

## 一、模块概述

本模块封装了世界杯知识库的全部 Chroma 向量数据库操作。你（成员 B / Agent 后端）只需调用本模块的公开函数，无需关心 Chroma 底层细节。

### 1.1 架构位置

```
用户问题 → Agent 路由（你的 LangGraph）
              │
              ├─ 结构化查询 → SQLite (worldcup.db)
              │
              └─ 语义检索 → chroma_service.query_top_k()  ← 你调用我
                                │
                                ├─ extract_filters()  提取过滤条件
                                ├─ BGE Embedding      中文语义编码
                                ├─ Chroma 检索        向量相似度
                                └─ enrich_result()    球队名+比分增强
```

### 1.2 两个 Collection

| Collection | 用途 | 调用时机 |
|-----------|------|---------|
| `world_cup_match_facts` | 964 条比赛事实，精确查询用 | 回答具体比赛、比分、胜负 |
| `world_cup_reports` | 比赛报告/长篇分析 | 回答总结、对比、评价类问题 |

---

## 二、快速开始（3 分钟集成）

```python
from backend.services.chroma_service import (
    extract_filters,      # Step 1: 提取过滤条件
    query_top_k,          # Step 2: 语义检索
    enrich_result,        # Step 3: 增强结果（可选）
    COLLECTION_FACTS,     # 常量："world_cup_match_facts"
    COLLECTION_REPORTS,   # 常量："world_cup_reports"
)

# ── 完整调用示例 ──

# Step 1: 从用户问题中提取结构化过滤条件
filters = extract_filters("2014年巴西队在半决赛的结果")
# → {"tournament_year": 2014, "team": "巴西", "team_id": "team_BRA", "stage": "半决赛"}

# Step 2: 语义检索（自动应用过滤条件 + query expansion）
results = query_top_k(
    query_text="2014年巴西队在半决赛的结果",
    k=5,                           # 返回 Top-5
    collection=COLLECTION_FACTS,   # 查哪个 collection
    filters=filters,               # 传入 Step 1 的过滤条件
)

# Step 3: 增强结果（球队名转中文 + SQLite 比分详情）
for item in results:
    enriched = enrich_result(item)
    print(enriched["team_names"])     # ["巴西", "德国"]   ← 而非 ["team_BRA", "team_GER"]
    print(enriched["match_detail"])   # {"score_display": "1:7", "venue": "...", ...}
```

---

## 三、核心 API

### 3.1 `extract_filters(query: str) → dict`

从自然语言中提取结构化过滤条件，缩小 Chroma 检索范围。

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 用户原始问题 |

**返回值**：
```python
{
    "tournament_year": 2014,       # int | None — 年份
    "team": "巴西",                 # str | None — 用户提到的球队中文名
    "team_id": "team_BRA",          # str | None — 标准化的 team_id（用于 Chroma 过滤）
    "stage": "半决赛",               # str | None — 比赛阶段
    "stage_hint": "淘汰赛",          # str | None — 宽泛阶段（不用于精确过滤）
    "rewritten_query": "巴西队结果",  # str — 去掉条件后的纯查询文本
}
```

**注意**：
- `stage_hint` 是"淘汰赛"这类宽泛词，**不会**用于 Chroma 的 where 过滤（因为淘汰赛包含多个具体阶段），仅作参考
- `rewritten_query` 已去掉年份/阶段等关键词，但保留球队名（用于语义匹配）
- 球队匹配依赖 `team_aliases.json`（255 条中英文别名），覆盖 1930-2022 全部参赛队

---

### 3.2 `query_top_k(query_text, k, collection, filters, use_query_rewrite) → list[dict]`

核心检索函数。返回最相关的 Top-K 个 chunk。

**参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query_text` | `str` | 必填 | 用户问题（可以是 rewritten_query） |
| `k` | `int` | `5` | 返回数量，范围 1-100 |
| `collection` | `str` | 必填 | `COLLECTION_FACTS` 或 `COLLECTION_REPORTS` |
| `filters` | `dict` | `None` | `extract_filters()` 的返回值，用于 metadata 过滤 |
| `use_query_rewrite` | `bool` | `True` | 是否启用多角度查询改写（提升召回率） |

**返回值**：
```python
[
    {
        "id": "M-2014-61",                    # match_id
        "document": "2014年世界杯半决赛...",    # chunk 文本
        "metadata": {
            "match_id": "M-2014-61",
            "tournament_year": 2014,
            "stage": "semi-finals",
            "team_ids": ["team_BRA", "team_GER"],
            "document_name": "FIFA World Cup 2014",
            "source_id": "src_csv_20260716_001",
        },
        "similarity": 0.4528,                 # 1 - distance，越大越相关
        "collection": "world_cup_match_facts",
    },
    # ... 最多 k 条，按 similarity 降序
]
```

**内部流程**：
1. `query_rewrite()` — 生成 2-3 个语义变体
2. 每个变体执行 Chroma 检索（用 filters 做 metadata 过滤）
3. 合并结果、去重、按相似度排序

---

### 3.3 `query_with_rerank(query_text, k, collection, filters, recall_k) → list[dict]`

完整检索管线：**粗筛（Chroma Top-20）→ 精排（Reranker Top-5）**。

**参数**：同 `query_top_k`，额外增加：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `recall_k` | `int` | `20` | 粗筛阶段召回数量（应 > k） |

**注意**：Reranker 需要额外下载模型（~1GB），当前环境未部署。调用时若 Reranker 不可用，**自动降级**为 `query_top_k` 的结果（不报错）。

**返回值**：同 `query_top_k`，额外增加 `rerank_score` 字段（仅在 Reranker 可用时）。

---

### 3.4 `enrich_result(item: dict) → dict`

增强 Chroma 原始结果：球队 ID 转中文名 + 从 SQLite 获取比赛详情。

**参数**：`query_top_k()` 返回的单条 item

**返回值**：在原 item 基础上增加：
```python
{
    # ... 原有字段 ...

    "team_names": ["巴西", "德国"],    # 新增：球队中文名列表

    "match_detail": {                  # 新增：SQLite 完整比赛详情
        "match_id": "M-2014-61",
        "tournament_year": 2014,
        "match_date": "2014-07-08",
        "stage": "semi-finals",
        "venue": "Estadio Mineirao",
        "home_team": "巴西",           # 已转为中文名
        "away_team": "德国",
        "score_display": "1:7",
        "winner": "德国",
        "result_type": "regulation",
    },
}
```

---

### 3.5 `format_result(item: dict, verbose: bool = False) → str`

将增强后的结果格式化为人类可读字符串，适合前端展示或调试日志。

**示例输出**：
```
[2014] semi-finals | 巴西 vs 德国 | 比分 1:7 | sim=0.4528 | regulation

# verbose=True 时额外输出:
  日期: 2014-07-08
  场馆: Estadio Mineirao
  摘要: 2014年世界杯半决赛，巴西队在Estadio Mineirao...
```

---

## 四、管理 API

### 4.1 `import_match_facts(json_path="match_facts.json") → int`

从 C 提供的 JSON 文件批量导入数据到 Chroma。**仅在数据更新时调用。**

```python
count = import_match_facts("match_facts.json")
# → 964 条导入完成
```

### 4.2 `add_chunks(chunks, collection) → int`

单条/小批量写入。C 的 `chunk.to_chroma_format()` 格式可直接传入。

### 4.3 `list_documents(collection) → list[dict]`

列出已存储的文档（按 match_id 去重）。

### 4.4 `delete_document(match_id, collection) → int`

按 match_id 删除指定比赛的所有 chunk。

### 4.5 `get_collection_stats() → dict`

获取两个 collection 的统计信息。

---

## 五、Integration 场景

### 场景 1：用户问精确事实（你的 Agent 路由到 RAG 分支）

```python
# 你的 Agent 判断意图为 "match_fact_query"
def handle_fact_query(user_message: str) -> dict:
    filters = extract_filters(user_message)
    results = query_top_k(
        query_text=filters.get("rewritten_query", user_message),
        k=5,
        collection=COLLECTION_FACTS,
        filters=filters,
    )

    # 增强 + 格式化
    enriched = [enrich_result(r) for r in results]
    sources = [format_result(r) for r in enriched]

    return {
        "intent": "match_fact_query",
        "answer": enriched[0]["document"] if enriched else "未找到相关比赛",
        "sources": sources,
        "matches": [r.get("match_detail") for r in enriched if r.get("match_detail")],
    }
```

### 场景 2：用户问总结/分析类问题

```python
def handle_summary_query(user_message: str) -> dict:
    results = query_top_k(
        query_text=user_message,
        k=5,
        collection=COLLECTION_REPORTS,  # ← 注意：查 reports
    )
    return {
        "intent": "summary_query",
        "chunks": [r["document"] for r in results],
        # 你把 chunks 拼进 Prompt 给 LLM 生成回答
    }
```

### 场景 3：混合查询（精确事实 + 语义补充）

```python
def handle_hybrid_query(user_message: str) -> dict:
    filters = extract_filters(user_message)

    # 结构化过滤 + 语义检索
    facts = query_top_k(user_message, k=3, collection=COLLECTION_FACTS, filters=filters)
    reports = query_top_k(user_message, k=2, collection=COLLECTION_REPORTS)

    # SQLite 精确校验（你的模块负责）
    # chroma_service 只提供语义检索，结构化精确查询请直接用 worldcup.db

    return {
        "facts": [enrich_result(f) for f in facts],
        "context_chunks": [r["document"] for r in reports],
    }
```

---

## 六、环境配置

### 6.1 Embedding 模式切换

```bash
# 默认模式：Chroma 内置 ONNX（离线可用，英文为主）
python your_agent.py

# BGE 模式：bge-small-zh-v1.5（中文精准，需先下载一次）
# Windows cmd:
set EMBEDDING_MODE=bge && python your_agent.py

# PowerShell:
$env:EMBEDDING_MODE="bge"; python your_agent.py
```

### 6.2 环境变量一览

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_MODE` | `default` | `default` 或 `bge` |
| `CHROMA_DATA_DIR` | `./backend/data/chroma_db` | 向量数据持久化目录 |
| `TEAM_ALIASES_PATH` | `team_aliases.json` | 球队别名文件路径 |

### 6.3 数据文件依赖

```
项目根目录/
├── match_facts.json      ← C 提供，964 条事实（导入到 Chroma）
├── team_aliases.json     ← C 提供，85 队别名映射（query rewrite 用）
├── worldcup.db           ← C 提供，结构化数据库（enrich_result 用）
└── backend/data/chroma_db/  ← D 维护，Chroma 持久化目录
```

---

## 七、错误处理

本模块所有公开函数在出现异常时：

- **参数错误**（空 query、非法 k 值等）：抛出 `ValueError`
- **数据不存在**：返回空列表 `[]` 或 `0`
- **文件/网络不可用**：通过 logger 输出警告，**不抛出异常**，优雅降级
- **Reranker 不可用**：自动回退到 Chroma 原始排序

**建议你在调用侧统一包一层 try-except**：
```python
try:
    results = query_top_k(...)
except ValueError as e:
    # 参数错误，返回友好提示
    return {"status": "error", "message": str(e)}
except Exception as e:
    # 未知错误，记录日志
    logger.error(f"Chroma 查询异常: {e}")
    return {"status": "error", "message": "系统内部错误"}
```

---

## 八、分⼯边界

| 事项 | 谁负责 | 说明 |
|------|--------|------|
| Chroma 语义检索 | D（本模块） | 你只管调 `query_top_k()` |
| 结构化精确查询（SQL） | B（你） | 直接查 `worldcup.db`，如 `SELECT * FROM matches WHERE ...` |
| Agent 路由/意图识别 | B（你） | 判断走 SQL 还是 Chroma |
| Prompt 拼装 + LLM 调用 | E | E 用你提供的结果拼 Prompt |
| 数据提供 | C | match_facts.json / worldcup.db / team_aliases.json |

**重要**：精确的球队信息查询（如"列出德国队所有比赛"）建议直接查 SQLite，Chroma 更适合语义模糊匹配（如"巴西那次惨案是哪场比赛"）。

---

## 九、性能参考

| 指标 | 值 |
|------|-----|
| Chroma 数据量 | 964 chunks，512 维向量 |
| 单次查询延迟（BGE） | ~30-50ms |
| 含 query expansion 延迟 | ~100ms |
| 含 Reranker 延迟（待部署） | ~500ms |
| 首次加载 BGE 模型 | ~10s（仅一次，后续缓存） |

---

> **有任何问题随时找我（成员 D）联调。**
