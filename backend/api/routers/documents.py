"""GET /api/documents — registered/indexed source documents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_provider
from backend.repositories.protocols import FrontendDataProvider
from backend.schemas.common import DocumentFilters
from backend.schemas.response import ApiResponse, ok
from backend.schemas.responses import DocumentsData

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=ApiResponse[DocumentsData])
async def list_documents(
    status: str | None = Query(default=None, description="pending / parsed / failed"),
    data_version: str | None = Query(default=None, description="数据版本"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    provider: FrontendDataProvider = Depends(get_provider),
) -> ApiResponse[dict]:
    """Return indexed source documents and their parse status."""
    filters = DocumentFilters(status=status, data_version=data_version)
    result = provider.list_documents(filters, page=page, page_size=page_size)
    return ok(data=result)
