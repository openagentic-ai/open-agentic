"""API tests for knowledge routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.db.session import get_db
from openagentic.knowledge import service
from openagentic.main import app


@pytest.fixture
async def knowledge_api_client(monkeypatch):
    now = datetime.now(timezone.utc)
    state: dict[str, dict] = {"docs": {}}

    async def fake_db():
        yield object()

    async def ingest_document(_db, *, filename, content_type, data, title=None, user_id=None):
        doc_id = uuid.uuid4()
        doc = SimpleNamespace(
            id=doc_id,
            user_id=user_id,
            title=title or filename,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            status="ready",
            error_message=None,
            chunk_count=1,
            metadata_json={},
            created_at=now,
            updated_at=now,
        )
        state["docs"][str(doc_id)] = doc
        return doc

    async def list_documents(_db, *, limit=100):
        return list(state["docs"].values())[:limit]

    async def delete_document_by_id(_db, document_id):
        return state["docs"].pop(str(document_id), None) is not None

    async def search_knowledge(_db, *, query, top_k=5):
        if not query:
            return []
        return [
            {
                "document_id": uuid.uuid4(),
                "title": "doc-a",
                "chunk_index": 0,
                "content": "matched text",
                "score": 0.88,
            }
        ][:top_k]

    monkeypatch.setattr(service, "ingest_document", ingest_document)
    monkeypatch.setattr(service, "list_documents", list_documents)
    monkeypatch.setattr(service, "delete_document_by_id", delete_document_by_id)
    monkeypatch.setattr(service, "search_knowledge", search_knowledge)

    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_knowledge_upload_list_search_delete(knowledge_api_client):
    client = knowledge_api_client
    upload = await client.post(
        "/api/knowledge/documents/upload",
        files={"file": ("note.txt", b"hello world", "text/plain")},
        data={"title": "my note"},
    )
    assert upload.status_code == 200
    doc_id = upload.json()["id"]

    listed = await client.get("/api/knowledge/documents?limit=20")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    searched = await client.post("/api/knowledge/search", json={"query": "hello", "top_k": 3})
    assert searched.status_code == 200
    assert searched.json()["results"]

    deleted = await client.delete(f"/api/knowledge/documents/{doc_id}")
    assert deleted.status_code == 200
