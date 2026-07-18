"""Health check endpoint — indicates the FastAPI process is alive."""

from __future__ import annotations

import sys

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return minimal health status. Does NOT imply C/D/E are ready."""
    major, minor = sys.version_info[:2]
    return {
        "status": "ok",
        "service": "world-cup-rag-agent-backend",
        "version": "0.1.0",
        "python": f"{major}.{minor}",
    }
