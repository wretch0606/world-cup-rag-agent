"""Health check endpoint — indicates the FastAPI process is alive."""

from __future__ import annotations

import sys

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.schemas.response import ApiResponse, ok

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    """Minimal health payload. Does NOT imply C/D/E are ready."""

    status: str = "ok"
    service: str = "world-cup-rag-agent-backend"
    version: str = "0.1.0"
    python: str = Field(default_factory=lambda: f"{sys.version_info[0]}.{sys.version_info[1]}")

    model_config = {"extra": "forbid"}


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check() -> ApiResponse[HealthData]:
    """Return minimal health status."""
    return ok(data=HealthData())
