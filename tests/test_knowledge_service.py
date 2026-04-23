"""Unit tests for knowledge service helpers."""

from __future__ import annotations

import pytest

from openagentic.knowledge import service


def test_split_text_chunks_produces_overlap():
    text = "A" * 2200
    chunks = service.split_text_chunks(text, chunk_size=800, overlap=200)
    assert len(chunks) >= 3
    assert all(chunks)


@pytest.mark.asyncio
async def test_generate_embedding_falls_back_when_provider_errors(monkeypatch):
    async def _raise(*args, **kwargs):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(service.litellm, "aembedding", _raise)
    vector = await service.generate_embedding("hello world")
    assert isinstance(vector, list)
    assert len(vector) == service.EMBEDDING_DIMENSION
