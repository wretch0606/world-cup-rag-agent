"""POST /api/agent/query — agent query endpoint (mock or langgraph)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

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
) -> ApiResponse[dict]:
    """Process a natural-language question and return answer + facts + graph."""
    trace_id = get_trace_id()
    result = agent_service.query(body.model_dump(), trace_id)
    return ok(data=result)
