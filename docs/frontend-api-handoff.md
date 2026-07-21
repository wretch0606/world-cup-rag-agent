# Frontend API Handoff — B → A 交接文档

> **日期**: 2026-07-19 | **契约版本**: `frontend-api-v1.0` | **状态**: A 联调中

---

## 1. 启动

```bash
cd world-cup-rag-agent
uv sync
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- 使用 Mock Provider（默认）：无需数据库
- 使用 SQLite Provider：设置 `FRONTEND_DATA_MODE=sqlite` + `WORLD_CUP_DB_PATH=path/to/worldcup_v2.db`

---

## 2. Base URL

```
http://localhost:8000/api
```

| 资源 | URL |
|---|---|
| Swagger | `http://localhost:8000/docs` |
| OpenAPI | `http://localhost:8000/openapi.json` |

---

## 3. 八个接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务存活 |
| GET | `/api/filter-options` | 筛选栏选项（年份/球队/阶段/结果类型） |
| GET | `/api/matches` | 比赛列表（多选筛选 + 分页） |
| GET | `/api/matches/{match_id}` | 比赛详情 + 时间线 + 来源 |
| GET | `/api/teams/{team_id}/relations` | 球队交手关系 + 统计 + 图 |
| GET | `/api/graph` | D3.js 关系图（节点 + 边） |
| GET | `/api/documents` | 来源文档列表 |
| POST | `/api/agent/query` | 自然语言问答 |

---

## 4. curl 速查

```bash
# Health
curl http://localhost:8000/api/health

# 筛选选项
curl http://localhost:8000/api/filter-options

# 比赛列表（2022 年 + 阿根廷）
curl "http://localhost:8000/api/matches?years=2022&team_ids=team_ARG&page=1&page_size=20"

# 仅看点球大战
curl "http://localhost:8000/api/matches?has_penalties=true"

# 比赛详情
curl http://localhost:8000/api/matches/M-2022-64

# 球队关系
curl "http://localhost:8000/api/teams/team_ARG/relations?year_from=2018&year_to=2022"

# D3 图（限制 10 条边）
curl "http://localhost:8000/api/graph?limit=10"

# 文档列表
curl http://localhost:8000/api/documents

# 问答
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question":"2022年世界杯决赛结果是什么？"}'
```

---

## 5. 统一响应

```json
{
  "success": true,
  "code": "OK",
  "message": "查询成功",
  "data": { ... },
  "trace_id": "uuid-v4",
  "timestamp": "2026-07-19T12:00:00Z"
}
```

Axios 读取路径：`response.data.data`

---

## 6. 错误码

| HTTP | code | retryable | 场景 |
|---|---|---|---|
| 200 | `OK` | — | 正常 |
| 400 | `BAD_REQUEST` | false | 无法解析的请求 |
| 404 | `MATCH_NOT_FOUND` | false | 比赛不存在 |
| 404 | `TEAM_NOT_FOUND` | false | 球队不存在 |
| 404 | `NOT_FOUND` | false | 路径不存在 |
| 422 | `VALIDATION_ERROR` | false | 参数校验失败 |
| 500 | `INTERNAL_ERROR` | true | 服务内部错误 |

错误响应额外包含 `retryable` 和 `details` 字段。

---

## 7. null 规则

| 场景 | 值 |
|---|---|
| 未知对象 | `null` |
| 空集合 | `[]` |
| 无加时赛 | `after_extra_time: null` |
| 无点球 | `penalties: null`, `penalty_display: null` |
| 未校准置信度 | `confidence: null` |
| Mock 来源 URL | `null` |

---

## 8. Trace ID

- 响应头 `X-Trace-ID` 与 JSON `trace_id` 一致
- 联调时把 `trace_id` 发给 B 定位问题
- 客户端可传 `X-Trace-ID`（≤64 字符，`[a-zA-Z0-9_-]`）

---

## 9. 多选查询参数

使用同名参数重复编码：

```text
/api/matches?years=2018&years=2022&team_ids=team_ARG&team_ids=team_FRA
```

**不要**用逗号拼接：`years=2018,2022`。

---

## 10. Vite 开发代理

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 11. TypeScript 调用示例

```ts
interface ApiResponse<T> {
  success: boolean;
  code: string;
  message: string;
  data: T;
  trace_id: string;
  timestamp: string;
}

// 初始化
const [filterOpts, matches, graph] = await Promise.all([
  fetch("/api/filter-options").then(r => r.json()),
  fetch("/api/matches?page=1&page_size=20").then(r => r.json()),
  fetch("/api/graph?limit=100").then(r => r.json()),
]);

// 提问
const resp = await fetch("/api/agent/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "2022年世界杯决赛结果是什么？",
    filters: { years: [2022] },
  }),
}).then(r => r.json());

// 从 fact 或 edge 获取 match_id 后打开详情
const matchId = resp.data.facts[0].match_id;
const detail = await fetch(`/api/matches/${matchId}`).then(r => r.json());
```

---

## 12. Mock 边界

当前默认运行在 `FRONTEND_DATA_MODE=mock` + `AGENT_MODE=mock`。

| 组件 | 状态 |
|---|---|
| 比赛筛选/详情/图/关系 | Mock Provider（5 场自洽比赛） |
| 问答 | MockAgentService（4 分支） |
| C 的 SQLite | 可通过环境变量切换 |
| D 的 Chroma | 未接入 |
| E 的 RAG | 未接入 |
| LangGraph | 未接入 |
| 会话持久化 | 未实现 |

所有 Mock 响应标记 `data_status="mock"` + `MOCK_DATA` warning。

---

## 13. 下一步

A 联调确认后，下一步为 **v2.0 Step 10**: 真实 B→E→D 集成（LangGraph + RAG）。
