"""POST /api/agent/query — agent query endpoint (mock or langgraph)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from backend.application.langgraph_agent_service import RAGFatalError
from backend.dependencies import get_agent_service
from backend.middleware.trace import get_trace_id
from backend.schemas.agent import AgentQueryRequest
from backend.schemas.response import ApiResponse, ok
from backend.schemas.responses import AgentQueryData

router = APIRouter(tags=["agent"])


@router.post("/agent/query", response_model=ApiResponse[AgentQueryData])
async def agent_query(
    request: Request,
    body: AgentQueryRequest,
    agent_service: object = Depends(get_agent_service),
) -> ApiResponse[dict] | JSONResponse:
    """Process a natural-language question and return answer + facts + graph."""
    import datetime as _dt

    trace_id = get_trace_id()
    try:
        result = agent_service.query(body.model_dump(), trace_id)
    except RAGFatalError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "data": None,
                "trace_id": trace_id,
                "timestamp": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
                "retryable": exc.retryable,
                "details": [],
            },
        )
    return ok(data=result)
