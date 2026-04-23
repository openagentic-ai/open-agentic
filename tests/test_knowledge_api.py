"""API tests for knowledge routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.knowledge import service
from openagentic.main import app


@pytest.fixture
async def knowledge_api_client(monkeypatch):
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async def fake_db():
        yield object()

    async def fake_current_user():
        return SimpleNamespace(id=user_id)

    async def list_knowledge_bases(_db, uid):
        assert uid == user_id
        return [
            SimpleNamespace(
                id=kb_id,
                name="kb-demo",
                description=None,
                embedding_model="nomic-embed-text",
                chunk_size=500,
                chunk_overlap=50,
                document_count=1,
                created_at=now,
                updated_at=now,
            )
        ]

    async def create_knowledge_base(**kwargs):
        return SimpleNamespace(
            id=kb_id,
            name=kwargs["name"],
            description=kwargs["description"],
            embedding_model=kwargs["embedding_model"],
            chunk_size=kwargs["chunk_size"],
            chunk_overlap=kwargs["chunk_overlap"],
            document_count=0,
            created_at=now,
            updated_at=now,
        )

    async def get_knowledge_base(_db, in_kb_id, _uid):
        if in_kb_id != kb_id:
            return None
        return SimpleNamespace(
            id=kb_id,
            name="kb-demo",
            description=None,
            embedding_model="nomic-embed-text",
            chunk_size=500,
            chunk_overlap=50,
            document_count=1,
            created_at=now,
            updated_at=now,
        )

    async def delete_knowledge_base(_db, in_kb_id, _uid):
        return in_kb_id == kb_id

    async def add_document(**kwargs):
        if kwargs["kb_id"] != kb_id:
            raise ValueError("Knowledge base not found or access denied")
        return SimpleNamespace(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename=kwargs["filename"],
            content_type=kwargs["content_type"],
            chunk_count=2,
            status="completed",
            created_at=now,
        )

    async def list_documents(_db, in_kb_id, _uid):
        if in_kb_id != kb_id:
            raise ValueError("Knowledge base not found or access denied")
        return [
            SimpleNamespace(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="note.txt",
                content_type="text/plain",
                chunk_count=2,
                status="completed",
                created_at=now,
            )
        ]

    async def delete_document(_db, in_doc_id, _uid):
        return in_doc_id == doc_id

    async def search(**kwargs):
        if kwargs["kb_id"] != kb_id:
            raise ValueError("Knowledge base not found or access denied")
        return [
            {
                "id": "chunk-1",
                "content": "matched text",
                "chunk_index": 0,
                "document_id": str(doc_id),
                "score": 0.88,
                "rerank_score": 0.92,
            }
        ]

    async def add_documents_batch(**kwargs):
        if kwargs["kb_id"] != kb_id:
            raise ValueError("Knowledge base not found or access denied")
        return [
            {
                "index": 0,
                "filename": "batch-a.txt",
                "status": "completed",
                "document_id": str(uuid.uuid4()),
                "error": None,
            },
            {
                "index": 1,
                "filename": "batch-b.txt",
                "status": "failed",
                "document_id": None,
                "error": "embedding timeout",
            },
        ]

    async def optimize_index(**kwargs):
        if kwargs["kb_id"] != kb_id:
            raise ValueError("Knowledge base not found or access denied")
        return ["idx_chunks_kb_embedding_ivfflat", "idx_chunks_kb_id_chunk_idx"]

    monkeypatch.setattr(service, "list_knowledge_bases", list_knowledge_bases)
    monkeypatch.setattr(service, "create_knowledge_base", create_knowledge_base)
    monkeypatch.setattr(service, "get_knowledge_base", get_knowledge_base)
    monkeypatch.setattr(service, "delete_knowledge_base", delete_knowledge_base)
    monkeypatch.setattr(service, "add_document", add_document)
    monkeypatch.setattr(service, "list_documents", list_documents)
    monkeypatch.setattr(service, "delete_document", delete_document)
    monkeypatch.setattr(service, "search", search)
    monkeypatch.setattr(service, "add_documents_batch", add_documents_batch)
    monkeypatch.setattr(service, "optimize_index", optimize_index)

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = fake_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, kb_id, doc_id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_knowledge_base_crud_and_document_search(knowledge_api_client):
    client, kb_id, doc_id = knowledge_api_client

    create_kb = await client.post("/api/knowledge/", json={"name": "kb-demo"})
    assert create_kb.status_code == 201

    list_kb = await client.get("/api/knowledge/")
    assert list_kb.status_code == 200
    assert len(list_kb.json()) == 1

    add_doc = await client.post(
        f"/api/knowledge/{kb_id}/documents",
        json={"filename": "note.txt", "content": "hello world", "content_type": "text/plain"},
    )
    assert add_doc.status_code == 201
    assert add_doc.json()["status"] == "completed"

    list_docs = await client.get(f"/api/knowledge/{kb_id}/documents")
    assert list_docs.status_code == 200
    assert list_docs.json()[0]["id"] == str(doc_id)

    searched = await client.post(f"/api/knowledge/{kb_id}/search", json={"query": "hello", "top_k": 3})
    assert searched.status_code == 200
    assert searched.json()[0]["score"] > 0
    assert searched.json()[0]["rerank_score"] > 0

    deleted = await client.delete(f"/api/knowledge/{kb_id}/documents/{doc_id}")
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_knowledge_batch_upload_and_index_optimize(knowledge_api_client):
    client, kb_id, _ = knowledge_api_client

    batch_resp = await client.post(
        f"/api/knowledge/{kb_id}/documents/batch",
        json={
            "documents": [
                {"filename": "batch-a.txt", "content": "alpha"},
                {"filename": "batch-b.txt", "content": "beta"},
            ],
            "stop_on_error": False,
        },
    )
    assert batch_resp.status_code == 201
    payload = batch_resp.json()
    assert payload["total"] == 2
    assert payload["succeeded"] == 1
    assert payload["failed"] == 1

    optimize_resp = await client.post(f"/api/knowledge/{kb_id}/optimize-index")
    assert optimize_resp.status_code == 200
    assert optimize_resp.json()["applied"] is True
    assert optimize_resp.json()["indexes"]


@pytest.mark.asyncio
async def test_knowledge_api_returns_404_for_unknown_knowledge_base(knowledge_api_client):
    client, _, _ = knowledge_api_client
    missing_id = uuid.uuid4()
    resp = await client.post(
        f"/api/knowledge/{missing_id}/search",
        json={"query": "hello", "top_k": 1},
    )
    assert resp.status_code == 404
