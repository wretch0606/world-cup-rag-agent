"""GET /api/filter-options — left sidebar filter options."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.response import ApiResponse, ok

router = APIRouter(tags=["filters"])


@router.get("/filter-options", response_model=ApiResponse[dict])
async def get_filter_options(
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return tournaments, teams, stages and result types for the filter sidebar."""
    data = provider.get_filter_options()
    return ok(data=data)
