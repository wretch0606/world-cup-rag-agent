# Backend

用于 FastAPI、LangGraph、结构化事实查询、Chroma 检索、重排与回答生成。

## 启动

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：
- Swagger 文档：<http://localhost:8000/docs>
- OpenAPI Schema：<http://localhost:8000/openapi.json>
- Health Check：<http://localhost:8000/api/health>
