# Frontend API Contract v1.0

> **版本**: v1.0
> **状态**: 已冻结
> **日期**: 2026-07-18
> **适用范围**: Vue 3 前端与 FastAPI 后端之间的 HTTP API 契约
> **公共前缀**: `/api`

---

## 0. 当前前端状态

截至本契约冻结时：
- `frontend/` 目录仅含 README，Vue 3 / D3.js 源码尚未提交
- 前端页面和 Mock 展示可以先完成，但真实 HTTP API 尚未接入
- 本契约作为前端开发接口的唯一基准，B 将严格按本文档实现后端
- 前端读取统一响应中的数据路径为 `response.data.data`

---

## 1. 通用约定

### 1.1 公共前缀

所有业务 API 统一使用 `/api` 前缀。本轮不同时维护 `/api/v1` 作为另一套正式路径。

### 1.2 JSON 字段命名

所有 JSON 字段使用 `snake_case`。

### 1.3 空值规则

| 场景 | 返回值 |
|---|---|
| 未知/不存在的对象 | `null` |
| 没有数据的集合 | `[]` |
| 没有加时赛 | `after_extra_time: null` |
| 没有点球大战 | `penalties: null` |
| 空数组过滤条件 | `[]`（表示不应用该条件） |

`0` 不能用来表示"未知"。

### 1.4 统一响应外壳

所有接口（包括错误响应）使用统一外壳：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {},
  "trace_id": "trace-example-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | boolean | 请求是否成功 |
| `code` | string | 稳定业务码，前端应依赖此字段判断状态 |
| `message` | string | 人类可读的描述信息 |
| `data` | object / null | 业务数据载荷 |
| `trace_id` | string | 请求链路追踪 ID，由服务端生成 |
| `timestamp` | string | ISO 8601 UTC 时间戳 |

错误响应在此固定字段基础上额外包含 `retryable` 和 `details`。

### 1.5 Mock 数据标识

所有 Mock 数据必须通过以下方式之一明确标识：
- 业务数据载荷中包含 `"data_status": "mock"`
- 响应中包含结构化 `MOCK_DATA` warning

Mock 来源不得冒充真实 FIFA 来源，`url` 可以为 `null`。

### 1.6 内部数据隔离

以下内部字段不得暴露给前端：
- D 的 `vector_distance`、`rerank_score`、`retrieval_rank`、`rerank_rank`
- LangGraph 内部 State 对象
- Prompt 全文、API Key、数据库连接串、服务器绝对路径

### 1.7 图数据约定

- 所有可点击图边必须包含唯一 `id` 和 `match_id`
- 边的 `match_id` 必须能成功调用 `GET /api/matches/{match_id}`
- 一场比赛一条边，同两支球队多次交手不能互相覆盖
- 方向建议：胜负已决时 `winner_team_id` → 负者；平局时 home → away 且 `winner_team_id = null`

### 1.8 时间线约定

- 问答接口（`POST /api/agent/query`）**不包含**完整时间线，只返回相关 `match_id`
- 比赛详情接口（`GET /api/matches/{match_id}`）独立返回完整时间线
- 缺少逐轮点球数据时 `shootout.available = false`，`shootout.events = []`，禁止伪造

### 1.9 比分对象结构化

比分对象必须区分以下口径：

| 字段 | 类型 | 说明 |
|---|---|---|
| `regular_time` | {home, away} / null | 90 分钟常规时间比分 |
| `after_extra_time` | {home, away} / null | 加时结束累计比分，无加时赛为 null |
| `penalties` | {home, away} / null | 点球大战比分，无点球为 null |
| `display` | string | 对用户展示的正式比分，如 `"3:3"` |
| `penalty_display` | string / null | 点球比分展示，如 `"4:2"`，必须与正式比分分开 |

点球比赛的正式比分和点球比分必须分离，不得把点球比分计入正式比赛进球数。

### 1.10 分页约定

列表接口统一使用：

| 参数 | 默认值 | 最大值 | 说明 |
|---|---|---|---|
| `page` | 1 | — | 页码，从 1 开始 |
| `page_size` | 20 | 100 | 每页条数 |

合法筛选无结果时返回 HTTP 200 和空 `items`，而非 404。非法 `page_size` 返回 422。

---

## 2. 枚举定义

### 2.1 比赛阶段 (stage)

| 值 | 中文名称 |
|---|---|
| `group` | 小组赛 |
| `round_of_16` | 1/8决赛 |
| `quarter_final` | 1/4决赛 |
| `semi_final` | 半决赛 |
| `third_place` | 三四名决赛 |
| `final` | 决赛 |

后端契约统一使用英文枚举值，中文名称通过 `stage_name` 或 `label` 返回。

### 2.2 结果类型 (result_type)

| 值 | 说明 |
|---|---|
| `regulation` | 90 分钟常规时间分出胜负 |
| `extra_time` | 加时赛后分出胜负 |
| `penalties` | 点球大战决出晋级 |
| `draw` | 平局（90 分钟平局且无加时/点球） |

### 2.3 球队 ID 编码规则

格式：`team_{FIFA_CODE}`。例如：`team_ARG`（阿根廷）、`team_FRA`（法国）、`team_BRA`（巴西）。

---

## 3. 接口定义

---

### 3.1 `GET /api/health`

**职责**：表示 FastAPI 进程可用。不表示 C/D/E 或数据库已就绪。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `GET` |
| 路径参数 | 无 |
| 查询参数 | 无 |
| 成功状态码 | `200` |

**成功响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "服务正常运行",
  "data": {
    "status": "ok",
    "service": "world-cup-rag-agent-backend",
    "version": "0.1.0",
    "python": "3.12"
  },
  "trace_id": "trace-health-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.status` | string | 固定 `"ok"` |
| `data.service` | string | 服务标识名称 |
| `data.version` | string | 服务版本号 |
| `data.python` | string | Python 主版本号 |

---

### 3.2 `GET /api/filter-options`

**职责**：返回前端左侧筛选栏所需的年份、球队、阶段和结果类型选项。数据来自 Mock Provider（接入 C 后替换为真实数据）。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `GET` |
| 路径参数 | 无 |
| 查询参数 | 无 |
| 成功状态码 | `200` |

**成功响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "tournaments": [
      { "year": 2022, "label": "2022 卡塔尔世界杯", "host": "卡塔尔" },
      { "year": 2018, "label": "2018 俄罗斯世界杯", "host": "俄罗斯" }
    ],
    "teams": [
      { "team_id": "team_ARG", "name": "阿根廷" },
      { "team_id": "team_FRA", "name": "法国" },
      { "team_id": "team_CRO", "name": "克罗地亚" },
      { "team_id": "team_BRA", "name": "巴西" },
      { "team_id": "team_GER", "name": "德国" },
      { "team_id": "team_ENG", "name": "英格兰" },
      { "team_id": "team_ESP", "name": "西班牙" },
      { "team_id": "team_NED", "name": "荷兰" },
      { "team_id": "team_POR", "name": "葡萄牙" },
      { "team_id": "team_MAR", "name": "摩洛哥" },
      { "team_id": "team_JPN", "name": "日本" },
      { "team_id": "team_KOR", "name": "韩国" }
    ],
    "stages": [
      { "value": "group", "label": "小组赛", "order": 1 },
      { "value": "round_of_16", "label": "1/8决赛", "order": 2 },
      { "value": "quarter_final", "label": "1/4决赛", "order": 3 },
      { "value": "semi_final", "label": "半决赛", "order": 4 },
      { "value": "third_place", "label": "三四名决赛", "order": 5 },
      { "value": "final", "label": "决赛", "order": 6 }
    ],
    "result_types": [
      { "value": "regulation", "label": "常规时间" },
      { "value": "extra_time", "label": "加时赛" },
      { "value": "penalties", "label": "点球大战" },
      { "value": "draw", "label": "平局" }
    ]
  },
  "trace_id": "trace-filter-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.data_status` | string | `"mock"` 表示当前为 Mock 数据 |
| `data.tournaments` | array | 世界杯届次列表 |
| `data.tournaments[].year` | integer | 举办年份 |
| `data.tournaments[].label` | string | 展示标签 |
| `data.tournaments[].host` | string / null | 主办国，未知时为 null |
| `data.teams` | array | 球队列表 |
| `data.teams[].team_id` | string | 规范球队 ID |
| `data.teams[].name` | string | 球队中文名称 |
| `data.stages` | array | 阶段列表，按 order 升序 |
| `data.stages[].value` | string | 阶段枚举值 |
| `data.stages[].label` | string | 中文显示名称 |
| `data.stages[].order` | integer | 排序序号 |
| `data.result_types` | array | 结果类型列表 |
| `data.result_types[].value` | string | 结果类型枚举值 |
| `data.result_types[].label` | string | 中文显示名称 |

---

### 3.3 `GET /api/matches`

**职责**：支持多选筛选和分页的比赛列表，驱动前端时间线摘要。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `GET` |
| 路径参数 | 无 |
| 查询参数 | `years`, `team_ids`, `stages`, `result_types`, `include_penalties`, `page`, `page_size` |
| 成功状态码 | `200` |
| 错误状态码 | `422`（参数校验失败） |

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `years` | integer[] | 否 | `[]` | 世界杯年份，多选 |
| `team_ids` | string[] | 否 | `[]` | 球队 ID，多选 |
| `stages` | string[] | 否 | `[]` | 阶段枚举值，多选 |
| `result_types` | string[] | 否 | `[]` | 结果类型，多选 |
| `include_penalties` | boolean | 否 | `true` | 是否包含点球决胜的比赛 |
| `page` | integer | 否 | `1` | 页码 |
| `page_size` | integer | 否 | `20` | 每页条数，最大 100 |

**成功响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
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
        "winner_team": {
          "team_id": "team_ARG",
          "name": "阿根廷"
        }
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
      "include_penalties": true
    }
  },
  "trace_id": "trace-matches-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**空结果响应**（合法筛选无结果返回 200）：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20,
    "applied_filters": {
      "years": [1930],
      "team_ids": [],
      "stages": ["final"],
      "result_types": [],
      "include_penalties": true
    }
  },
  "trace_id": "trace-matches-002",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.items` | array | 比赛摘要列表 |
| `data.items[].match_id` | string | 比赛唯一标识 |
| `data.items[].tournament_year` | integer | 世界杯年份 |
| `data.items[].match_date` | string | 比赛日期 YYYY-MM-DD |
| `data.items[].stage` | string | 阶段枚举值 |
| `data.items[].stage_name` | string | 阶段中文名称 |
| `data.items[].home_team` | object | 主队简要信息 |
| `data.items[].home_team.team_id` | string | 球队 ID |
| `data.items[].home_team.name` | string | 球队中文名 |
| `data.items[].away_team` | object | 客队简要信息 |
| `data.items[].score` | object | 结构化比分（见 1.9） |
| `data.items[].result_type` | string | 结果类型枚举值 |
| `data.items[].winner_team` | object / null | 胜者信息，平局时为 null |
| `data.total` | integer | 符合条件的总数 |
| `data.page` | integer | 当前页码 |
| `data.page_size` | integer | 每页条数 |
| `data.applied_filters` | object | 实际生效的筛选条件回显 |

---

### 3.4 `GET /api/matches/{match_id}`

**职责**：返回单场比赛的完整详情和时间线，驱动前端底部比赛详情面板。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `GET` |
| 路径参数 | `match_id`（string，比赛唯一标识） |
| 查询参数 | 无 |
| 成功状态码 | `200` |
| 错误状态码 | `404`（`MATCH_NOT_FOUND`） |

**成功响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "match_id": "M-2022-64",
    "tournament_year": 2022,
    "match_date": "2022-12-18",
    "stage": "final",
    "stage_name": "决赛",
    "venue": "卢塞尔体育场",
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
    "winner_team": {
      "team_id": "team_ARG",
      "name": "阿根廷"
    },
    "timeline": {
      "regular_time": [
        {
          "event_id": "evt-001",
          "minute": 23,
          "minute_label": "23'",
          "period": "first_half",
          "team_id": "team_ARG",
          "player": "Lionel Messi",
          "event_type": "goal_penalty",
          "score_after_event": { "home": 1, "away": 0 },
          "source_ids": ["source-001"]
        },
        {
          "event_id": "evt-002",
          "minute": 36,
          "minute_label": "36'",
          "period": "first_half",
          "team_id": "team_ARG",
          "player": "Angel Di Maria",
          "event_type": "goal",
          "score_after_event": { "home": 2, "away": 0 },
          "source_ids": ["source-001"]
        },
        {
          "event_id": "evt-003",
          "minute": 80,
          "minute_label": "80'",
          "period": "second_half",
          "team_id": "team_FRA",
          "player": "Kylian Mbappe",
          "event_type": "goal_penalty",
          "score_after_event": { "home": 2, "away": 1 },
          "source_ids": ["source-001"]
        },
        {
          "event_id": "evt-004",
          "minute": 81,
          "minute_label": "81'",
          "period": "second_half",
          "team_id": "team_FRA",
          "player": "Kylian Mbappe",
          "event_type": "goal",
          "score_after_event": { "home": 2, "away": 2 },
          "source_ids": ["source-001"]
        }
      ],
      "extra_time": [
        {
          "event_id": "evt-005",
          "minute": 108,
          "minute_label": "108'",
          "period": "extra_time",
          "team_id": "team_ARG",
          "player": "Lionel Messi",
          "event_type": "goal",
          "score_after_event": { "home": 3, "away": 2 },
          "source_ids": ["source-001"]
        },
        {
          "event_id": "evt-006",
          "minute": 118,
          "minute_label": "118'",
          "period": "extra_time",
          "team_id": "team_FRA",
          "player": "Kylian Mbappe",
          "event_type": "goal_penalty",
          "score_after_event": { "home": 3, "away": 3 },
          "source_ids": ["source-001"]
        }
      ],
      "shootout": {
        "available": false,
        "home_score": 4,
        "away_score": 2,
        "events": [],
        "message": "当前仅提供点球大战总比分，逐轮点球数据暂不可用。"
      }
    },
    "sources": [
      {
        "source_id": "source-001",
        "title": "FIFA World Cup 2022 Official Report",
        "url": null,
        "source_type": "mock",
        "data_version": "2026-07-16-v1"
      }
    ]
  },
  "trace_id": "trace-detail-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**404 响应**：

```json
{
  "success": false,
  "code": "MATCH_NOT_FOUND",
  "message": "未找到 match_id 为 M-9999-99 的比赛",
  "data": null,
  "trace_id": "trace-detail-404",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.match_id` | string | 比赛唯一标识 |
| `data.venue` | string / null | 比赛场地 |
| `data.timeline` | object | 结构化时间线 |
| `data.timeline.regular_time` | array | 常规时间事件列表 |
| `data.timeline.extra_time` | array | 加时赛事件列表 |
| `data.timeline.shootout` | object | 点球大战信息 |
| `data.timeline.shootout.available` | boolean | 是否有逐轮数据 |
| `data.timeline.shootout.events` | array | 逐轮点球事件，不可用时为空 |
| `data.timeline.shootout.message` | string | 点球数据可用性说明 |
| `data.sources` | array | 数据来源列表 |
| `data.sources[].source_id` | string | 来源唯一标识 |
| `data.sources[].title` | string | 来源名称 |
| `data.sources[].url` | string / null | 来源 URL，Mock 时为 null |
| `data.sources[].source_type` | string | 来源类型，Mock 时为 `"mock"` |

**Event 对象**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `event_id` | string | 事件唯一标识 |
| `minute` | integer | 比赛分钟数 |
| `minute_label` | string | 分钟展示标签，如 `"23'"`, `"45+2'"` |
| `period` | string | 比赛时段：`first_half` / `second_half` / `extra_time` |
| `team_id` | string | 事件所属球队 ID |
| `player` | string | 球员姓名 |
| `event_type` | string | 事件类型：`goal` / `goal_penalty` / `goal_own` / `yellow_card` / `red_card` / `substitution` |
| `score_after_event` | object / null | 事件后的比分，不可用时为 null |
| `source_ids` | array | 事件来源 ID 列表 |

---

### 3.5 `GET /api/graph`

**职责**：为 D3.js 提供可筛选的比赛关系图数据。图数据从比赛数据派生，与 `/api/matches` 保持一致。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `GET` |
| 路径参数 | 无 |
| 查询参数 | `years`, `team_ids`, `stages`, `result_types`, `include_penalties`, `limit` |
| 成功状态码 | `200` |

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `years` | integer[] | 否 | `[]` | 世界杯年份 |
| `team_ids` | string[] | 否 | `[]` | 球队 ID |
| `stages` | string[] | 否 | `[]` | 阶段枚举值 |
| `result_types` | string[] | 否 | `[]` | 结果类型 |
| `include_penalties` | boolean | 否 | `true` | 是否包含点球比赛 |
| `limit` | integer | 否 | `100` | 最大边数，防止前端渲染过载 |

**成功响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "scope": "filtered_matches",
    "nodes": [
      { "id": "team_ARG", "name": "阿根廷", "type": "team" },
      { "id": "team_FRA", "name": "法国", "type": "team" },
      { "id": "team_CRO", "name": "克罗地亚", "type": "team" },
      { "id": "team_MAR", "name": "摩洛哥", "type": "team" }
    ],
    "edges": [
      {
        "id": "edge-M-2022-64",
        "source": "team_ARG",
        "target": "team_FRA",
        "type": "match",
        "match_id": "M-2022-64",
        "tournament_year": 2022,
        "stage": "final",
        "stage_name": "决赛",
        "result_type": "penalties",
        "winner_team_id": "team_ARG",
        "label": "决赛 3:3 (4:2)"
      },
      {
        "id": "edge-M-2022-63",
        "source": "team_CRO",
        "target": "team_MAR",
        "type": "match",
        "match_id": "M-2022-63",
        "tournament_year": 2022,
        "stage": "third_place",
        "stage_name": "三四名决赛",
        "result_type": "regulation",
        "winner_team_id": "team_CRO",
        "label": "三四名决赛 2:1"
      },
      {
        "id": "edge-M-2022-62",
        "source": "team_ARG",
        "target": "team_CRO",
        "type": "match",
        "match_id": "M-2022-62",
        "tournament_year": 2022,
        "stage": "semi_final",
        "stage_name": "半决赛",
        "result_type": "regulation",
        "winner_team_id": "team_ARG",
        "label": "半决赛 3:0"
      },
      {
        "id": "edge-M-2022-61",
        "source": "team_FRA",
        "target": "team_MAR",
        "type": "match",
        "match_id": "M-2022-61",
        "tournament_year": 2022,
        "stage": "semi_final",
        "stage_name": "半决赛",
        "result_type": "regulation",
        "winner_team_id": "team_FRA",
        "label": "半决赛 2:0"
      }
    ],
    "stats": {
      "total_nodes": 4,
      "total_edges": 4
    },
    "applied_filters": {
      "years": [2022],
      "team_ids": [],
      "stages": [],
      "result_types": [],
      "include_penalties": true
    }
  },
  "trace_id": "trace-graph-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**空结果响应**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "scope": "filtered_matches",
    "nodes": [],
    "edges": [],
    "stats": {
      "total_nodes": 0,
      "total_edges": 0
    },
    "applied_filters": {
      "years": [1930],
      "team_ids": [],
      "stages": ["final"],
      "result_types": [],
      "include_penalties": true
    }
  },
  "trace_id": "trace-graph-002",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.scope` | string | 图数据范围，`"filtered_matches"` 表示筛选后的比赛 |
| `data.nodes` | array | 节点列表 |
| `data.nodes[].id` | string | 节点唯一标识（team_id） |
| `data.nodes[].name` | string | 球队中文名称 |
| `data.nodes[].type` | string | 固定 `"team"` |
| `data.edges` | array | 边列表 |
| `data.edges[].id` | string | 边唯一标识，格式 `edge-{match_id}` |
| `data.edges[].source` | string | 起始节点 ID |
| `data.edges[].target` | string | 目标节点 ID |
| `data.edges[].type` | string | 固定 `"match"` |
| `data.edges[].match_id` | string | 关联比赛 ID，可用于调用详情接口 |
| `data.edges[].tournament_year` | integer | 赛事年份 |
| `data.edges[].stage` | string | 阶段枚举值 |
| `data.edges[].stage_name` | string | 阶段中文名称 |
| `data.edges[].result_type` | string | 结果类型 |
| `data.edges[].winner_team_id` | string / null | 胜者 team_id，平局为 null |
| `data.edges[].label` | string | 边展示标签 |
| `data.stats` | object | 图统计信息 |
| `data.applied_filters` | object | 实际生效的筛选条件回显 |

---

### 3.6 `POST /api/agent/query`

**职责**：接收用户自然语言问题，返回答案、事实、来源和与答案直接相关的图数据。当前为 Mock 闭环，不接入真实 LangGraph / LLM / C / D / E。

| 项目 | 内容 |
|---|---|
| HTTP 方法 | `POST` |
| 路径参数 | 无 |
| 请求体 Content-Type | `application/json` |
| 成功状态码 | `200` |
| 错误状态码 | `422`（参数校验失败） |

**请求体**：

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
    "include_penalties": true
  },
  "debug": false
}
```

**请求字段说明**：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `question` | string | 是 | — | 用户问题，去除首尾空白后非空，≤2000 字符 |
| `session_id` | string / null | 否 | `null` | 会话 ID，本轮不持久化会话 |
| `filters` | object | 否 | `{}` | 前端筛选条件 |
| `filters.years` | integer[] | 否 | `[]` | 世界杯年份 |
| `filters.team_ids` | string[] | 否 | `[]` | 球队 ID |
| `filters.stages` | string[] | 否 | `[]` | 阶段枚举值 |
| `filters.result_types` | string[] | 否 | `[]` | 结果类型 |
| `filters.match_ids` | string[] | 否 | `[]` | 指定比赛 ID |
| `filters.include_penalties` | boolean | 否 | `true` | 是否包含点球比赛 |
| `debug` | boolean | 否 | `false` | 调试模式，默认关闭，不得泄露内部对象 |

**成功响应 — 已知事实问题（status: ok）**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "status": "ok",
    "intent": "exact_fact",
    "route": "sql_exact",
    "answer": "2022年世界杯决赛，阿根廷与法国在90分钟内战成2:2，加时赛结束后为3:3。阿根廷最终在点球大战中以4:2获胜，夺得2022年卡塔尔世界杯冠军。",
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
        "home_team_id": "team_ARG",
        "home_team_name": "阿根廷",
        "away_team_id": "team_FRA",
        "away_team_name": "法国",
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
        "title": "FIFA World Cup 2022 Official Report",
        "url": null,
        "source_type": "mock",
        "data_version": "2026-07-16-v1",
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
          "type": "match",
          "match_id": "M-2022-64",
          "tournament_year": 2022,
          "stage": "final",
          "stage_name": "决赛",
          "result_type": "penalties",
          "winner_team_id": "team_ARG",
          "label": "决赛 3:3 (4:2)"
        }
      ]
    },
    "applied_filters": {
      "years": [2022],
      "team_ids": ["team_ARG", "team_FRA"],
      "stages": ["final"],
      "result_types": ["penalties"],
      "match_ids": [],
      "include_penalties": true
    },
    "confidence": null,
    "warnings": [
      {
        "code": "MOCK_DATA",
        "message": "当前为前端联调Mock响应，尚未接入真实C/D/E与LangGraph",
        "component": "mock_agent_service"
      }
    ],
    "timing": {
      "total_ms": 15
    }
  },
  "trace_id": "trace-query-001",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**成功响应 — 需要澄清（status: clarification_required）**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "status": "clarification_required",
    "intent": "exact_fact",
    "route": "clarification",
    "answer": "请补充信息：您想查询哪一届世界杯的决赛结果？",
    "needs_clarification": true,
    "clarification_question": "请选择世界杯年份。",
    "facts": [],
    "sources": [],
    "graph": {
      "scope": "answer_facts",
      "nodes": [],
      "edges": []
    },
    "applied_filters": {
      "years": [],
      "team_ids": [],
      "stages": [],
      "result_types": [],
      "match_ids": [],
      "include_penalties": true
    },
    "confidence": null,
    "warnings": [
      {
        "code": "MOCK_DATA",
        "message": "当前为前端联调Mock响应，尚未接入真实C/D/E与LangGraph",
        "component": "mock_agent_service"
      }
    ],
    "timing": {
      "total_ms": 8
    }
  },
  "trace_id": "trace-query-002",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**成功响应 — 空结果（status: empty）**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "status": "empty",
    "intent": "exact_fact",
    "route": "not_found",
    "answer": "当前知识库中没有足够信息回答您的问题。",
    "needs_clarification": false,
    "clarification_question": null,
    "facts": [],
    "sources": [],
    "graph": {
      "scope": "answer_facts",
      "nodes": [],
      "edges": []
    },
    "applied_filters": {
      "years": [],
      "team_ids": [],
      "stages": [],
      "result_types": [],
      "match_ids": [],
      "include_penalties": true
    },
    "confidence": null,
    "warnings": [
      {
        "code": "MOCK_DATA",
        "message": "当前为前端联调Mock响应，尚未接入真实C/D/E与LangGraph",
        "component": "mock_agent_service"
      },
      {
        "code": "NO_RESULT",
        "message": "没有可靠事实或证据回答该问题。",
        "component": "mock_agent_service"
      }
    ],
    "timing": {
      "total_ms": 6
    }
  },
  "trace_id": "trace-query-003",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**成功响应 — 普通聊天（intent: general_chat）**：

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": {
    "data_status": "mock",
    "status": "ok",
    "intent": "general_chat",
    "route": "general_chat",
    "answer": "你好！我是世界杯知识问答助手，可以回答关于世界杯比赛、比分、球队和晋级关系的问题。请告诉我你想了解什么。",
    "needs_clarification": false,
    "clarification_question": null,
    "facts": [],
    "sources": [],
    "graph": {
      "scope": "answer_facts",
      "nodes": [],
      "edges": []
    },
    "applied_filters": {
      "years": [],
      "team_ids": [],
      "stages": [],
      "result_types": [],
      "match_ids": [],
      "include_penalties": true
    },
    "confidence": null,
    "warnings": [
      {
        "code": "MOCK_DATA",
        "message": "当前为前端联调Mock响应，尚未接入真实C/D/E与LangGraph",
        "component": "mock_agent_service"
      }
    ],
    "timing": {
      "total_ms": 5
    }
  },
  "trace_id": "trace-query-004",
  "timestamp": "2026-07-17T12:00:00Z"
}
```

**422 响应 — 空问题**：

```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "message": "question 字段不能为空",
  "data": null,
  "trace_id": "trace-query-422",
  "timestamp": "2026-07-17T12:00:00Z",
  "retryable": false,
  "details": [
    {
      "field": "question",
      "error": "question 去除首尾空白后不能为空"
    }
  ]
}
```

**Agent Query 响应字段说明**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.data_status` | string | `"mock"` 表示当前为 Mock 数据 |
| `data.status` | string | `ok` / `clarification_required` / `empty` / `error` |
| `data.intent` | string | 意图分类：`exact_fact` / `general_chat` 等 |
| `data.route` | string | 路由路径：`sql_exact` / `clarification` / `not_found` / `general_chat` |
| `data.answer` | string | 对用户的最终回答文本 |
| `data.needs_clarification` | boolean | 是否需要用户补充信息 |
| `data.clarification_question` | string / null | 需要澄清时的追问 |
| `data.facts` | array | 答案采用的结构化事实列表 |
| `data.sources` | array | 答案采用并去重后的来源列表 |
| `data.graph` | object | 与答案直接相关的图数据（仅含相关比赛） |
| `data.graph.scope` | string | 图数据范围：`"answer_facts"` |
| `data.applied_filters` | object | 实际生效的筛选条件回显 |
| `data.confidence` | number / null | 置信度，未校准前为 null |
| `data.warnings` | array | 结构化告警信息 |
| `data.timing` | object | 全链路耗时 |
| `data.timing.total_ms` | integer | 总耗时（毫秒），非负数 |

**Fact 对象**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `fact_type` | string | 事实类型：`match_result` / `relation` / `summary` |
| `fact_id` | string | 事实唯一标识 |
| `match_id` | string / null | 关联比赛 ID，非比赛事实可为 null |
| `tournament_year` | integer | 赛事年份（match_result 类型时） |
| `stage` | string | 阶段枚举值（match_result 类型时） |
| `stage_name` | string | 阶段中文名称（match_result 类型时） |
| `home_team_id` | string | 主队 ID（match_result 类型时） |
| `home_team_name` | string | 主队中文名（match_result 类型时） |
| `away_team_id` | string | 客队 ID（match_result 类型时） |
| `away_team_name` | string | 客队中文名（match_result 类型时） |
| `score_display` | string | 正式比分展示 |
| `penalty_score` | string / null | 点球比分展示 |
| `result_type` | string | 结果类型 |
| `winner_team_id` | string / null | 胜者 ID |
| `text` | string | 事实陈述文本 |
| `source_ids` | array | 来源 ID 列表 |

**Source 对象**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `source_id` | string | 来源唯一标识 |
| `title` | string | 来源名称 |
| `url` | string / null | 来源 URL，Mock 时为 null |
| `source_type` | string | 来源类型，Mock 时为 `"mock"` |
| `data_version` | string | 数据版本号 |
| `used_for_fact_ids` | array | 该来源支持的事实 ID 列表 |

**Warning 对象**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | string | 告警代码 |
| `message` | string | 告警说明 |
| `component` | string | 产生告警的组件 |

---

## 4. 错误码汇总

| 业务码 | HTTP 状态码 | 说明 |
|---|---|---|
| `OK` | 200 | 成功 |
| `VALIDATION_ERROR` | 422 | 请求参数校验失败 |
| `MATCH_NOT_FOUND` | 404 | 比赛 ID 不存在 |
| `NOT_FOUND` | 404 | 通用资源未找到 |
| `INTERNAL_ERROR` | 500 | 服务内部未捕获异常 |

---

## 5. 分页约定汇总

| 规则 | 说明 |
|---|---|
| `page` 默认值 | `1` |
| `page_size` 默认值 | `20` |
| `page_size` 最大值 | `100` |
| 非法 `page_size` | 返回 422 |
| 合法筛选无结果 | 返回 200，`items: []`, `total: 0` |
| 空筛选条件 | 等于不应用该条件（`[]`） |

---

## 6. 前端调用流程建议

```text
页面初始化             → GET /api/filter-options
用户选择筛选条件       → GET /api/matches 或 GET /api/graph
用户点击比赛           → GET /api/matches/{match_id}（展示详情和时间线）
用户提问               → POST /api/agent/query
从 fact/edge 获取 match_id → GET /api/matches/{match_id}（查看详情）
```

---

## 7. 当前 Mock 边界声明

本契约冻结的接口在步骤 02-08 中将以 **Mock Provider** 实现，所有 Mock 响应通过 `data_status: "mock"` 或 `MOCK_DATA` warning 明确标识。

以下能力在本轮**不实现**，将在下一阶段"真实 C/D/E Adapter 与 LangGraph 集成"中接入：

- FastAPI → C 的正式 SQLite 数据库
- FastAPI → D 的 Chroma 向量检索与 Reranker
- FastAPI → E 的 RAG 答案生成与事实融合
- FastAPI → LangGraph 意图路由与编排
- 登录注册、后台管理、数据上传、SSE、WebSocket、会话持久化
