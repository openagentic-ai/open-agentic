"""Unit tests for knowledge service helpers."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from openagentic.knowledge import service
from openagentic.knowledge.chunker import chunk_text


def test_chunk_text_handles_empty_and_short_text():
    assert chunk_text("") == []
    assert chunk_text("short", chunk_size=10, chunk_overlap=2) == ["short"]


def test_chunk_text_respects_overlap_boundary():
    text = "A" * 1200
    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 4
    assert max(len(c) for c in chunks) <= 300


def test_merge_multimodal_content_includes_part_summaries():
    merged = service._merge_multimodal_content(  # noqa: SLF001
        "base text",
        [
            {"type": "image", "name": "chart.png", "text": "sales trend"},
            {"type": "audio", "name": "meeting.wav", "url": "https://example.com/a.wav"},
        ],
    )
    assert "base text" in merged
    assert "[image] chart.png" in merged
    assert "sales trend" in merged
    assert "source=https://example.com/a.wav" in merged


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def execute(self, _stmt):
        raise AssertionError("execute() should not be called in this test")


class _FakeDocument:
    def __init__(self, **kwargs):
        self.id = uuid.uuid4()
        self.__dict__.update(kwargs)
        self.chunk_count = kwargs.get("chunk_count", 0)
        self.status = kwargs.get("status", "pending")


class _FakeChunk:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.mark.asyncio
async def test_add_document_marks_failed_when_embedding_errors(monkeypatch):
    db = _FakeDB()
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def fake_get_kb(_db, _kb_id, _user_id):
        return SimpleNamespace(
            id=kb_id,
            embedding_model="nomic-embed-text",
            chunk_size=500,
            chunk_overlap=50,
            document_count=0,
        )

    async def fake_embed_texts(_chunks, model):
        raise RuntimeError(f"embedding failed: {model}")

    monkeypatch.setattr(service, "get_knowledge_base", fake_get_kb)
    monkeypatch.setattr(service, "chunk_text", lambda _c, chunk_size, chunk_overlap: ["a", "b"])
    monkeypatch.setattr(service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(service, "Document", _FakeDocument)
    monkeypatch.setattr(service, "Chunk", _FakeChunk)

    with pytest.raises(RuntimeError, match="embedding failed"):
        await service.add_document(
            db=db,
            kb_id=kb_id,
            user_id=user_id,
            filename="bad.txt",
            content="hello",
        )

    doc = db.added[0]
    assert doc.status == "failed"


@pytest.mark.asyncio
async def test_search_raises_when_knowledge_base_not_owned(monkeypatch):
    async def fake_get_kb(_db, _kb_id, _uid):
        return None

    monkeypatch.setattr(service, "get_knowledge_base", fake_get_kb)

    with pytest.raises(ValueError, match="not found"):
        await service.search(
            db=SimpleNamespace(),
            kb_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            query="hello",
            top_k=3,
        )


@pytest.mark.asyncio
async def test_add_documents_batch_continues_on_error(monkeypatch):
    async def fake_add_document(**kwargs):
        if kwargs["filename"] == "bad.txt":
            raise RuntimeError("bad doc")
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(service, "add_document", fake_add_document)

    items = await service.add_documents_batch(
        db=SimpleNamespace(),
        kb_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        documents=[
            {"filename": "ok.txt", "content": "hello"},
            {"filename": "bad.txt", "content": "world"},
        ],
        stop_on_error=False,
    )
    assert len(items) == 2
    assert items[0].status == "completed"
    assert items[1].status == "failed"
