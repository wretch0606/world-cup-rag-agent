"""FastAPI application factory for world-cup-rag-agent."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from backend.api.health import router as health_router
from backend.api.routers.filters import router as filters_router
from backend.api.routers.matches import router as matches_router
from backend.api.routers.agent import router as agent_router
from backend.api.routers.documents import router as documents_router
from backend.api.routers.graph import router as graph_router
from backend.api.routers.teams import router as teams_router
from backend.config import settings
from backend.middleware.logging import LoggingMiddleware
from backend.middleware.trace import TraceMiddleware, get_trace_id
from backend.schemas.response import ErrorDetail, error
from backend.schemas.responses import ErrorResponse

# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("backend")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        responses={
            422: {
                "model": ErrorResponse,
                "description": "Validation Error — unified error envelope",
            }
        },
    )

    # ---- Middleware (order: outermost first → innermost last) ----
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TraceMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routes ----
    app.include_router(health_router, prefix="/api")
    app.include_router(filters_router, prefix="/api")
    app.include_router(matches_router, prefix="/api")
    app.include_router(teams_router, prefix="/api")
    app.include_router(graph_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")

    # ---- Exception handlers ----
    _register_exception_handlers(app)

    return app


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = get_trace_id()
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in e.get("loc", ())),
                error=e.get("msg", ""),
            )
            for e in exc.errors()
        ]
        logger.warning(
            "validation_error path=%s trace_id=%s errors=%d",
            request.url.path,
            trace_id,
            len(details),
        )
        return error(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            status_code=422,
            retryable=False,
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        trace_id = get_trace_id()
        code_map: dict[int, str] = {404: "NOT_FOUND"}
        code = code_map.get(exc.status_code, "ERROR")
        logger.info(
            "http_exception path=%s status=%d trace_id=%s",
            request.url.path,
            exc.status_code,
            trace_id,
        )
        return error(
            code=code,
            message=exc.detail or "资源未找到",
            status_code=exc.status_code,
            retryable=False,
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = get_trace_id()
        logger.exception(
            "unhandled_error path=%s trace_id=%s error=%s",
            request.url.path,
            trace_id,
            exc,
        )
        return error(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            status_code=500,
            retryable=True,
        )


# Module-level app instance for uvicorn
app = create_app()
