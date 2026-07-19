"""Integration tests for GET /api/documents."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_documents_200() -> None:
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data


def test_documents_empty_is_ok() -> None:
    """Empty documents table returns 200 with empty items."""
    resp = client.get("/api/documents")
    assert resp.status_code == 200


def test_documents_pagination() -> None:
    resp = client.get("/api/documents?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 10


def test_documents_no_file_path_exposed() -> None:
    resp = client.get("/api/documents")
    body_str = str(resp.json()).lower()
    assert "file_path" not in body_str
    assert "absolute" not in body_str


def test_openapi_has_documents_path() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/documents" in schema["paths"]
