"""Tests for vector retrieval rerank and index helpers."""

from __future__ import annotations

import pytest

from openagentic.knowledge import search


def test_rerank_prioritizes_query_overlap():
    rows = [
        {"id": "a", "content": "nothing relevant", "chunk_index": 0, "document_id": "d1", "score": 0.95},
        {"id": "b", "content": "hello world and more hello", "chunk_index": 1, "document_id": "d2", "score": 0.70},
    ]
    ranked = search._rerank_results("hello world", rows)  # noqa: SLF001
    assert ranked[0]["id"] == "b"
    assert ranked[0]["rerank_score"] >= ranked[1]["rerank_score"]


class _FakeDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        raise RuntimeError("unsupported db")


@pytest.mark.asyncio
async def test_ensure_vector_indexes_gracefully_handles_unsupported_db():
    db = _FakeDB()
    indexes = await search.ensure_vector_indexes(db)
    assert indexes == []
    assert db.calls >= 1
