"""FastAPI application factory for world-cup-rag-agent."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.health import router as health_router
from backend.config import settings


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
    )

    # CORS — only allow configured origins, never * with credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes — all under /api prefix
    app.include_router(health_router, prefix="/api")

    return app


# Module-level app instance for uvicorn
app = create_app()
