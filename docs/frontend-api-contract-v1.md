# A↔B Frontend HTTP API Contract v1.0

> **契约版本**: `frontend-api-v1.0`
> **状态**: A 已按契约完成请求层；B 后端待实现和联调
> **日期**: 2026-07-19
> **请求方**: A：Vue 3 + TypeScript + D3.js 前端
> **提供方**: B：FastAPI + LangGraph/Service 编排层
> **公共前缀**: `/api`
> **数据格式**: JSON；UTF-8；字段统一 `snake_case`
> **冻结原则**: Swagger/OpenAPI 与本文件一致；禁止只靠聊天口头增加字段

本文件定义 A 发给 B 的 HTTP 请求以及 B 返回给 A 的公开响应。它不替代 B→E、E→D、D→E、E→B 的 RAG 内部契约，也不向前端暴露 LangGraph State、Chroma distance、rerank score、Prompt 或数据库内部字段。

---

## 1. 与 A 当前前端设计的对应关系

A 当前页面已完成 Vue 3 + TypeScript + D3.js 静态 Mock 重构，并已能触发真实 HTTP 请求：

| A 当前区域 | 当前代码中的数据 | 正式接口 |
|---|---|---|
| 左侧筛选栏 | `filterOptions`、`selectedFilters` | `GET /api/filter-options` |
| 问答输入与事实表 | `apiResponse.data`、`handleSendQuestion()` | `POST /api/agent/query` |
| 来源卡片 | `apiResponse.data.sources` | `POST /api/agent/query` 的 `sources` |
| D3 球队关系图 | `apiResponse.data.graph` | `GET /api/graph` 或问答响应中的小图 |
| 底部比赛时间线 | `timelineStages` | `GET /api/matches`，A 按 `stage` 分组 |
| 点击比赛展开详情 | `expandedMatchDetail` | `GET /api/matches/{match_id}` |

A 前端字段映射约定：

1. `selectedFilters.tournamentYears` 请求时映射为 `years`。
2. `selectedFilters.teamIds` 请求时映射为 `team_ids`。
3. `selectedFilters.resultTypes` 请求时映射为 `result_types`。
4. `selectedFilters.hasPenalties` 请求时映射为 `has_penalties`。
5. 筛选选项中的 `team_id` 映射到复选框使用的 `id`。
6. 比赛接口返回 `home_team/away_team` 对象，前端展示时读取其 `name`。
7. `confidence=null` 时显示"未评估"或隐藏该 Badge。
8. 问答、图和列表共用同一份筛选状态，筛选与问答联动。

---

## 2. 本期接口范围

### 2.1 A 页面必须接入

```text
GET  /api/health
GET  /api/filter-options
GET  /api/matches
GET  /api/matches/{match_id}
GET  /api/teams/{team_id}/relations
GET  /api/graph
GET  /api/documents
POST /api/agent/query
```

### 2.2 本期不属于 A 页面契约

`POST /api/kb/import` 属于管理/数据导入能力。当前 A 页面没有上传入口，且 C、D 的导入链仍需统一，因此本契约不冻结该接口。

---

## 3. 通用协议

### 3.1 成功响应外壳

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {},
  "trace_id": "trace-20260719-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

前端使用 Axios 时，业务数据读取路径为 `response.data.data`。

### 3.2 错误响应外壳

```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "message": "请求参数不合法。",
  "data": null,
  "trace_id": "trace-20260719-002",
  "timestamp": "2026-07-19T12:00:01Z",
  "retryable": false,
  "details": [
    {
      "field": "page_size",
      "reason": "必须小于或等于 100"
    }
  ]
}
```

### 3.3 HTTP、空值和时间约定

- 成功读取使用 `200 OK`。
- 请求 JSON 使用 `Content-Type: application/json`。
- 服务端在响应头返回 `X-Trace-ID`，且必须与 JSON 的 `trace_id` 一致。
- 时间使用 ISO 8601 UTC，例如 `2026-07-19T12:00:00Z`。
- 日期使用 `YYYY-MM-DD`；未知日期返回 `null`。
- 数组没有内容时返回 `[]`，不得返回 `null`。
- 可选对象或标量未知时返回 `null`，不得用空字符串或 `0` 代替未知。
- 合法筛选没有结果时返回 `200` 和空数组，不返回 `404`。
- JSON 数值保持数值类型，禁止把比分整数返回为字符串。
- B 不向 A 返回堆栈、SQL、服务器绝对路径、API Key、Prompt 或模型内部对象。

### 3.4 多选查询参数编码

数组查询参数使用"同名参数重复"形式：

```text
/api/matches?years=2018&years=2022&team_ids=team_ARG&team_ids=team_FRA&stages=final&page=1&page_size=20
```

A 不发送逗号拼接字符串，例如不得发送 `years=2018,2022`。

### 3.5 数据状态

| 值 | 含义 |
|---|---|
| `live` | 来自已配置的真实服务或 SQLite 数据 |
| `mock` | 仅供 A↔B 页面联调的确定性 Mock |
| `degraded` | 部分依赖不可用，但返回了安全的有限结果 |

Mock 响应必须同时包含 `data_status="mock"` 或 `MOCK_DATA` 告警。Mock 来源不得伪装成 FIFA 官方来源，URL 应为 `null`。

---

## 4. 公共枚举

### 4.1 StageEnum

| value | 中文显示 | 推荐顺序 |
|---|---|---:|
| `group` | 小组赛 | 10 |
| `second_group` | 第二阶段小组赛 | 20 |
| `round_of_16` | 1/8 决赛 | 30 |
| `quarter_final` | 1/4 决赛 | 40 |
| `semi_final` | 半决赛 | 50 |
| `third_place` | 三四名决赛 | 60 |
| `final_round` | 决赛循环赛 | 70 |
| `final` | 决赛 | 80 |

### 4.2 ResultTypeEnum

```text
regulation
extra_time
penalties
draw
```

`has_penalties=true` 的唯一语义是"只返回发生过点球大战的比赛"。是否把点球晋级计为统计胜利属于统计口径，不通过这个字段表达。

### 4.3 AgentStatus

```text
ok
empty
degraded
clarification_required
error
```

### 4.4 IntentEnum

```text
general_chat
match_result_query
match_relation_query
summary_query
comparison_query
role_chat
out_of_scope
```

### 4.5 RouteEnum

```text
general_chat
structured_query
rag_query
hybrid_query
role_agent
clarification
```

---

## 5. 公共数据对象

### 5.1 TeamRef

```json
{
  "team_id": "team_ARG",
  "name": "阿根廷"
}
```

### 5.2 ScoreBreakdown

```json
{
  "regular_time": {
    "home": 2,
    "away": 2
  },
  "after_extra_time": {
    "home": 3,
    "away": 3
  },
  "penalties": {
    "home": 4,
    "away": 2
  },
  "display": "3:3",
  "penalty_display": "4:2"
}
```

约束：

- `regular_time` 必须存在。
- 没有加时赛时 `after_extra_time=null`。
- 没有点球大战时 `penalties=null` 且 `penalty_display=null`。
- `display` 是正式比赛比分，不包含点球大战比分。
- 点球大战比赛仍可在正式比分上为平局。

### 5.3 SourceItem

```json
{
  "source_id": "source-kaggle-001",
  "title": "FIFA World Cup match dataset",
  "url": "https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset",
  "page": null,
  "document_id": null,
  "data_version": "2026-07-16-v2",
  "used_for_fact_ids": [
    "fact-M-2022-64-result"
  ]
}
```

`used_for_fact_ids` 在比赛详情接口中允许为空数组；在问答响应中应指出该来源支持哪些事实。

### 5.4 WarningItem

```json
{
  "code": "MOCK_DATA",
  "message": "当前为前端联调 Mock 响应。",
  "component": "mock_agent_service",
  "retryable": false
}
```

### 5.5 GraphNode 与 GraphEdge

```json
{
  "nodes": [
    {
      "id": "team_ARG",
      "name": "阿根廷",
      "type": "team"
    }
  ],
  "edges": [
    {
      "id": "edge-M-2022-64",
      "source": "team_ARG",
      "target": "team_FRA",
      "type": "match_result",
      "match_id": "M-2022-64",
      "tournament_year": 2022,
      "stage": "final",
      "stage_name": "决赛",
      "result_type": "penalties",
      "winner_team_id": "team_ARG",
      "label": "2022 决赛 3:3（点球4:2）"
    }
  ]
}
```

图规则：

- 一场比赛对应一条边，同一对球队多次交手不得互相覆盖。
- `edge.id` 和 `match_id` 必须稳定且唯一。
- 已决胜比赛方向为胜方→负方。
- 平局方向为主队→客队，同时 `winner_team_id=null`；A 不得仅凭方向推断胜负。
- 每个 `source/target` 都必须引用 `nodes` 中存在的节点。
- 每条边的 `match_id` 必须能够调用比赛详情接口。

---

## 6. 接口定义

### 6.1 GET `/api/health`

职责：检查 FastAPI 进程是否可访问。它不代表 SQLite、D、E、LLM 或 Chroma 一定就绪。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "服务可用",
  "data": {
    "status": "ok",
    "service": "world-cup-rag-agent-backend",
    "version": "0.1.0",
    "python": "3.12"
  },
  "trace_id": "trace-health-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

### 6.2 GET `/api/filter-options`

职责：返回 A 左侧筛选栏使用的全部可选项。A 不再硬编码年份、球队、阶段和结果类型。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "tournaments": [
      {
        "year": 2022,
        "label": "2022 卡塔尔世界杯",
        "host": "卡塔尔"
      }
    ],
    "teams": [
      {
        "team_id": "team_ARG",
        "name": "阿根廷"
      },
      {
        "team_id": "team_FRA",
        "name": "法国"
      }
    ],
    "stages": [
      {
        "value": "group",
        "label": "小组赛",
        "order": 10
      },
      {
        "value": "second_group",
        "label": "第二阶段小组赛",
        "order": 20
      },
      {
        "value": "round_of_16",
        "label": "1/8 决赛",
        "order": 30
      },
      {
        "value": "quarter_final",
        "label": "1/4 决赛",
        "order": 40
      },
      {
        "value": "semi_final",
        "label": "半决赛",
        "order": 50
      },
      {
        "value": "third_place",
        "label": "三四名决赛",
        "order": 60
      },
      {
        "value": "final_round",
        "label": "决赛循环赛",
        "order": 70
      },
      {
        "value": "final",
        "label": "决赛",
        "order": 80
      }
    ],
    "result_types": [
      {
        "value": "regulation",
        "label": "常规时间决胜"
      },
      {
        "value": "extra_time",
        "label": "加时赛决胜"
      },
      {
        "value": "penalties",
        "label": "点球大战决胜"
      },
      {
        "value": "draw",
        "label": "平局"
      }
    ]
  },
  "trace_id": "trace-filter-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

验收要求：年份倒序；`team_id` 唯一；球队按中文名或约定顺序稳定排序；阶段按 `order` 排序。

### 6.3 GET `/api/matches`

职责：按筛选条件返回比赛摘要，驱动 A 的底部时间线。返回平铺 `items`，由 A 按 `stage` 分组。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `years` | integer[] | `[]` | 多届年份 |
| `team_ids` | string[] | `[]` | 主队或客队命中任一球队 |
| `stages` | StageEnum[] | `[]` | 多阶段 |
| `result_types` | ResultTypeEnum[] | `[]` | 多结果类型 |
| `has_penalties` | boolean / null | `null` | `true` 仅看点球大战；`null` 不限制 |
| `page` | integer | `1` | 最小 1 |
| `page_size` | integer | `20` | 1—100 |

同一字段内使用 OR，不同字段之间使用 AND。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "items": [
      {
        "match_id": "M-2022-64",
        "tournament_year": 2022,
        "match_date": "2022-12-18",
        "stage": "final",
        "stage_name": "决赛",
        "home_team": {
          "team_id": "team_ARG",
          "name": "阿根廷"
        },
        "away_team": {
          "team_id": "team_FRA",
          "name": "法国"
        },
        "score": {
          "regular_time": { "home": 2, "away": 2 },
          "after_extra_time": { "home": 3, "away": 3 },
          "penalties": { "home": 4, "away": 2 },
          "display": "3:3",
          "penalty_display": "4:2"
        },
        "result_type": "penalties",
        "winner_team": { "team_id": "team_ARG", "name": "阿根廷" }
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "applied_filters": {
      "years": [2022],
      "team_ids": [],
      "stages": ["final"],
      "result_types": [],
      "has_penalties": null
    }
  },
  "trace_id": "trace-matches-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

空结果仍返回 `200`：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "applied_filters": {
      "years": [2099],
      "team_ids": [],
      "stages": [],
      "result_types": [],
      "has_penalties": null
    }
  },
  "trace_id": "trace-matches-empty-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

固定排序：`tournament_year DESC`、`match_date ASC`、阶段顺序 ASC、`match_id ASC`，保证分页稳定。

### 6.4 GET `/api/matches/{match_id}`

职责：返回单场比赛比分、事件、来源，驱动 A 点击时间线卡片后的展开详情。

路径参数：`match_id`，例如 `M-2022-64`。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "match_date": "2022-12-18",
    "stage": "final",
    "stage_name": "决赛",
    "venue": "Lusail Stadium",
    "city": "Lusail",
    "home_team": { "team_id": "team_ARG", "name": "阿根廷" },
    "away_team": { "team_id": "team_FRA", "name": "法国" },
    "score": {
      "regular_time": { "home": 2, "away": 2 },
      "after_extra_time": { "home": 3, "away": 3 },
      "penalties": { "home": 4, "away": 2 },
      "display": "3:3",
      "penalty_display": "4:2"
    },
    "result_type": "penalties",
    "winner_team": { "team_id": "team_ARG", "name": "阿根廷" },
    "timeline": {
      "regular_time": [],
      "extra_time": [],
      "shootout": {
        "available": false,
        "home_score": 4,
        "away_score": 2,
        "events": [],
        "message": "当前数据仅包含点球大战总比分，暂无逐轮罚球顺序。"
      }
    },
    "sources": [
      {
        "source_id": "source-kaggle-001",
        "title": "FIFA World Cup match dataset",
        "url": "https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset",
        "page": null,
        "document_id": null,
        "data_version": "2026-07-16-v2",
        "used_for_fact_ids": []
      }
    ]
  },
  "trace_id": "trace-match-detail-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

事件对象预留结构：

```json
{
  "event_id": "G-00001",
  "minute": 23,
  "minute_label": "23'",
  "period": "regular_time",
  "team_id": "team_ARG",
  "player": "Lionel Messi",
  "event_type": "penalty_goal",
  "score_after_event": { "home": 1, "away": 0 },
  "source_ids": ["source-kaggle-001"]
}
```

若没有逐轮点球数据，必须 `shootout.available=false` 且 `events=[]`，禁止使用大模型补全罚球顺序。未知比赛返回 `404 MATCH_NOT_FOUND`。

### 6.5 GET `/api/teams/{team_id}/relations`

职责：返回指定球队的交手、胜负和比分关系。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `year_from` | integer / null | `null` | 起始年份 |
| `year_to` | integer / null | `null` | 结束年份 |
| `opponent_id` | string / null | `null` | 指定对手 |
| `stages` | StageEnum[] | `[]` | 阶段筛选 |
| `result_types` | ResultTypeEnum[] | `[]` | 结果筛选 |
| `has_penalties` | boolean / null | `null` | 仅看点球大战 |
| `page` | integer | `1` | 最小 1 |
| `page_size` | integer | `20` | 1—100 |

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "team": { "team_id": "team_ARG", "name": "阿根廷" },
    "stats": {
      "matches": 3,
      "regulation_or_extra_time_wins": 1,
      "draws": 2,
      "penalty_advances": 2,
      "losses": 0
    },
    "matches": [],
    "graph": { "scope": "team_relations", "nodes": [], "edges": [] },
    "total": 3,
    "page": 1,
    "page_size": 20,
    "applied_filters": {
      "year_from": 1990,
      "year_to": 2022,
      "opponent_id": null,
      "stages": [],
      "result_types": [],
      "has_penalties": null
    }
  },
  "trace_id": "trace-relations-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

统计口径：点球大战晋级单列为 `penalty_advances`，不直接混入 `regulation_or_extra_time_wins`。未知球队返回 `404 TEAM_NOT_FOUND`。

### 6.6 GET `/api/graph`

职责：按与比赛列表相同的筛选条件返回 D3.js 图数据。

查询参数：`years`、`team_ids`、`stages`、`result_types`、`has_penalties` 与 `/api/matches` 一致；另有 `limit`，默认 100，范围 1—500，限制边数。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "scope": "filtered_matches",
    "nodes": [
      { "id": "team_ARG", "name": "阿根廷", "type": "team" },
      { "id": "team_FRA", "name": "法国", "type": "team" }
    ],
    "edges": [
      {
        "id": "edge-M-2022-64",
        "source": "team_ARG",
        "target": "team_FRA",
        "type": "match_result",
        "match_id": "M-2022-64",
        "tournament_year": 2022,
        "stage": "final",
        "stage_name": "决赛",
        "result_type": "penalties",
        "winner_team_id": "team_ARG",
        "label": "2022 决赛 3:3（点球4:2）"
      }
    ],
    "stats": { "node_count": 2, "edge_count": 1, "truncated": false },
    "applied_filters": {
      "years": [2022],
      "team_ids": [],
      "stages": ["final"],
      "result_types": [],
      "has_penalties": null
    }
  },
  "trace_id": "trace-graph-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

合法空图返回空 `nodes/edges` 和零统计。`truncated=true` 时 A 应显示"图数据已截断，请缩小筛选范围"。

### 6.7 GET `/api/documents`

职责：查看已经登记或索引的来源文档及处理状态。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `status` | string / null | `null` | `pending`、`parsed`、`failed` |
| `data_version` | string / null | `null` | 数据版本 |
| `page` | integer | `1` | 最小 1 |
| `page_size` | integer | `20` | 1—100 |

空结果示例：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "applied_filters": { "status": null, "data_version": null }
  },
  "trace_id": "trace-documents-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

文档存在时，每项至少包含：`document_id`、`title`、`source_id`、`file_type`、`parse_status`、`chunk_count`、`parsed_at`、`data_version`。不得把服务器本地绝对 `file_path` 暴露给 A。

### 6.8 POST `/api/agent/query`

职责：A 的唯一自然语言问答入口。B 负责验证筛选、生成 `trace_id`、路由精确事实/语义/混合问题并组装前端响应。

请求体：

```json
{
  "question": "2022年世界杯决赛结果是什么？",
  "session_id": null,
  "filters": {
    "years": [2022],
    "team_ids": ["team_ARG", "team_FRA"],
    "stages": ["final"],
    "result_types": ["penalties"],
    "match_ids": [],
    "has_penalties": true
  },
  "debug": false
}
```

请求约束：

- `question` 去除首尾空白后长度 1—2000。
- `session_id` 可空；当前版本不承诺会话持久化。
- `filters` 可省略；省略等价于全部空数组和 `has_penalties=null`。
- `debug=false` 为默认值；普通 A 页面不得通过 debug 获取内部 State。
- 未定义字段返回 `422 VALIDATION_ERROR`。

成功响应：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "live",
    "status": "ok",
    "intent": "match_result_query",
    "route": "structured_query",
    "answer": "2022年世界杯决赛，阿根廷与法国在90分钟内战成2:2，加时赛后为3:3；阿根廷在点球大战中以4:2获胜。",
    "needs_clarification": false,
    "clarification_question": null,
    "facts": [
      {
        "fact_type": "match_result",
        "fact_id": "fact-M-2022-64-result",
        "match_id": "M-2022-64",
        "tournament_year": 2022,
        "stage": "final",
        "stage_name": "决赛",
        "home_team": { "team_id": "team_ARG", "name": "阿根廷" },
        "away_team": { "team_id": "team_FRA", "name": "法国" },
        "score": {
          "regular_time": { "home": 2, "away": 2 },
          "after_extra_time": { "home": 3, "away": 3 },
          "penalties": { "home": 4, "away": 2 },
          "display": "3:3",
          "penalty_display": "4:2"
        },
        "result_type": "penalties",
        "winner_team": { "team_id": "team_ARG", "name": "阿根廷" },
        "text": "双方加时赛后战成3:3，阿根廷点球大战4:2获胜。",
        "source_ids": ["source-kaggle-001"]
      }
    ],
    "sources": [
      {
        "source_id": "source-kaggle-001",
        "title": "FIFA World Cup match dataset",
        "url": "https://www.kaggle.com/datasets/jahaidulislam/fifa-world-cup-1930-2022-all-match-dataset",
        "page": null,
        "document_id": null,
        "data_version": "2026-07-16-v2",
        "used_for_fact_ids": ["fact-M-2022-64-result"]
      }
    ],
    "graph": {
      "scope": "answer_facts",
      "nodes": [
        { "id": "team_ARG", "name": "阿根廷", "type": "team" },
        { "id": "team_FRA", "name": "法国", "type": "team" }
      ],
      "edges": [
        {
          "id": "edge-M-2022-64",
          "source": "team_ARG",
          "target": "team_FRA",
          "type": "match_result",
          "match_id": "M-2022-64",
          "tournament_year": 2022,
          "stage": "final",
          "stage_name": "决赛",
          "result_type": "penalties",
          "winner_team_id": "team_ARG",
          "label": "2022 决赛 3:3（点球4:2）"
        }
      ]
    },
    "applied_filters": {
      "years": [2022],
      "team_ids": ["team_ARG", "team_FRA"],
      "stages": ["final"],
      "result_types": ["penalties"],
      "match_ids": [],
      "has_penalties": true
    },
    "confidence": null,
    "warnings": [],
    "timing": {
      "routing_ms": 2,
      "sql_ms": 4,
      "retrieval_ms": 0,
      "generation_ms": 0,
      "total_ms": 6
    }
  },
  "trace_id": "trace-agent-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

问答图只包含答案直接使用的事实，完整筛选图由 A 单独调用 `/api/graph`。问答响应不返回完整比赛时间线；A 从 `fact.match_id` 调用比赛详情。

澄清状态仍返回 HTTP 200：

```json
{
  "success": true,
  "code": "OK",
  "message": "需要补充条件",
  "data": {
    "data_status": "live",
    "status": "clarification_required",
    "intent": "match_result_query",
    "route": "clarification",
    "answer": "请补充世界杯年份。",
    "needs_clarification": true,
    "clarification_question": "你想查询哪一届世界杯决赛？",
    "facts": [],
    "sources": [],
    "graph": { "scope": "answer_facts", "nodes": [], "edges": [] },
    "applied_filters": {
      "years": [],
      "team_ids": [],
      "stages": ["final"],
      "result_types": [],
      "match_ids": [],
      "has_penalties": null
    },
    "confidence": null,
    "warnings": [
      {
        "code": "NEED_CLARIFICATION",
        "message": "年份条件不足。",
        "component": "routing",
        "retryable": false
      }
    ],
    "timing": {
      "routing_ms": 2,
      "sql_ms": 0,
      "retrieval_ms": 0,
      "generation_ms": 0,
      "total_ms": 2
    }
  },
  "trace_id": "trace-agent-clarify-001",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

无可靠结果时使用 `status=empty`，`facts/sources/nodes/edges` 均为空，不得编造比分或来源。

---

## 7. 错误码和 HTTP 状态

| HTTP | code | 场景 | retryable |
|---:|---|---|---:|
| 400 | `BAD_REQUEST` | 无法解析的请求 | false |
| 404 | `MATCH_NOT_FOUND` | 比赛不存在 | false |
| 404 | `TEAM_NOT_FOUND` | 球队不存在 | false |
| 404 | `NOT_FOUND` | 其他路径不存在 | false |
| 422 | `VALIDATION_ERROR` | 参数、枚举或请求体校验失败 | false |
| 503 | `DATA_SOURCE_UNAVAILABLE` | SQLite/Provider 不可用且无法安全降级 | true |
| 504 | `UPSTREAM_TIMEOUT` | E/D/LLM 上游超时且无安全结果 | true |
| 500 | `INTERNAL_ERROR` | 未处理的服务端错误 | true |

业务上的 `empty`、`degraded`、`clarification_required` 不是 HTTP 错误，正常返回 200，并由 A 根据 `data.status` 展示。

---

## 8. A 的调用与状态更新约定

### 8.1 页面初始化

```text
1. GET /api/filter-options
2. GET /api/matches?page=1&page_size=20
3. GET /api/graph?limit=100
```

三次请求可并行；任何一个失败不得让整个页面白屏。A 应在对应区域显示错误和 `trace_id`。

### 8.2 筛选变化

```text
selectedFilters
  → 统一序列化为 query/filter DTO
  → 刷新 /api/matches
  → 刷新 /api/graph
  → 提问时复用同一 filters
```

### 8.3 提问

```text
输入 question
  → POST /api/agent/query
  → 更新意图、答案、事实、来源和 answer_facts 图
  → 点击 fact 或 edge
  → GET /api/matches/{match_id}
```

### 8.4 加载与竞态

- 发送请求期间禁用重复提交或取消前一次问答请求。
- 筛选快速变化时取消旧的列表/图请求，避免旧响应覆盖新筛选。
- 每个页面区域分别维护 `loading/error/data`。
- A 记录失败响应的 `trace_id`，联调时把它发给 B 定位。

---

## 9. A、B 冻结确认清单

### A 确认

- [ ] 接受公共前缀 `/api`，不同时维护 `/api/v1`。
- [ ] 接受统一响应外壳，并按 `data` 读取业务数据。
- [ ] 多选参数采用同名参数重复编码。
- [ ] 接受 `home_team/away_team` 对象，不要求后端重复返回扁平名称。
- [ ] 使用 `has_penalties`，不再使用含义模糊的 `include_penalties`。
- [ ] 支持 `second_group` 和 `final_round`。
- [ ] `confidence=null` 时不显示伪造百分比。
- [ ] edge/fact 点击后使用 `match_id` 调用详情接口。
- [ ] 当前静态 Mock URL 和固定 FIFA 来源会被移除。

### B 确认

- [ ] OpenAPI 模型与本文件字段一致，核心 DTO 不使用无约束 `dict`。
- [ ] `penalty_score=""` 对外规范化为 `null`。
- [ ] 不根据 `result_type=extra_time` 强行推断胜者；以 `winner_team_id` 为准。
- [ ] 图由统一比赛数据派生，不维护与比赛列表矛盾的独立常量。
- [ ] 每个 fact/source/edge 可追溯到稳定 ID。
- [ ] Mock 和 live 数据明确区分。
- [ ] 未校准前 `confidence=null`。
- [ ] 不暴露 D/E 内部检索分数和 LangGraph State。

### 共同确认

- [ ] A 使用实际页面完成正常、空结果、澄清、错误、点球和无来源场景验收。
- [ ] Swagger 示例与实际返回 JSON 一致。
- [ ] 字段变更必须修改契约版本、Pydantic 模型、TypeScript 类型和自动化测试。
- [ ] A、B 在文档中记录确认日期与确认人后，状态改为 `frontend-api-v1.0-frozen`。

---

## 10. 冻结后的变更规则

兼容性新增字段可以升级补丁版本；删除字段、重命名字段、改变类型、改变空值语义或改变图方向属于破坏性变更，必须升级主/次版本并由 A、B 重新确认。B、C、D、E 内部实现可以替换，但只要本契约未升级，A 不应被迫同步修改。
