"""POST /api/agent/query — mock agent query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.application.mock_agent_service import MockAgentService
from backend.middleware.trace import get_trace_id
from backend.schemas.agent import AgentQueryRequest
from backend.schemas.response import ApiResponse, ok

router = APIRouter(tags=["agent"])
_service = MockAgentService()


@router.post("/agent/query", response_model=ApiResponse[dict])
async def agent_query(request: Request, body: AgentQueryRequest) -> ApiResponse[dict]:
    """Process a natural-language question and return answer + facts + graph."""
    trace_id = get_trace_id()
    result = _service.query(body.model_dump(), trace_id)
    return ok(data=result)
