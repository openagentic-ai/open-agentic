"""Knowledge base service: ingest, chunk, embedding, and semantic retrieval."""

from __future__ import annotations

import hashlib
import math
import uuid

import litellm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.config import SETTINGS
from openagentic.core.llm.provider_config import get_provider_store
from openagentic.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus
from openagentic.knowledge.schemas import KnowledgeSearchResult

CHUNK_SIZE = 900
CHUNK_OVERLAP = 180
EMBEDDING_DIMENSION = 1536
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


def split_text_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text with simple overlap strategy for retrieval quality."""
    source = text.strip()
    if not source:
        return []
    if chunk_size <= overlap:
        overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    length = len(source)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = source[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(0, end - overlap)
    return chunks


def estimate_tokens(text: str) -> int:
    # Rough estimate; precise tokenizer is not required for MVP.
    return max(1, len(text) // 4)


def _deterministic_embedding(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Stable fallback embedding to keep ingestion available without external model."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for i in range(dimension):
        byte = seed[i % len(seed)]
        values.append((byte / 255.0) * 2.0 - 1.0)
    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]
    return values


async def generate_embedding(text: str) -> list[float]:
    """Try provider-backed embedding first, then fallback to deterministic local vector."""
    try:
        model, api_base, api_key = get_provider_store().resolve_runtime(
            SETTINGS.OPENAI_CHAT_MODEL or DEFAULT_EMBEDDING_MODEL
        )
        response = await litellm.aembedding(
            model=model,
            input=[text],
            api_base=api_base,
            api_key=api_key,
        )
        vector = response.data[0]["embedding"]
        if isinstance(vector, list) and len(vector) > 0:
            if len(vector) == EMBEDDING_DIMENSION:
                return [float(v) for v in vector]
    except Exception:
        pass
    return _deterministic_embedding(text)


async def ingest_document(
    db: AsyncSession,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    title: str | None = None,
    user_id: uuid.UUID | None = None,
) -> KnowledgeDocument:
    """Ingest a text document and build chunks + embeddings."""
    doc = KnowledgeDocument(
        user_id=user_id,
        title=(title or filename or "untitled").strip()[:255],
        filename=(filename or "unknown.txt").strip()[:255],
        content_type=(content_type or "text/plain").strip()[:100],
        size_bytes=len(data),
        status=KnowledgeDocumentStatus.processing,
        metadata_json={},
    )
    db.add(doc)
    await db.flush()

    try:
        text = data.decode("utf-8", errors="ignore").strip()
        chunks = split_text_chunks(text)
        if not chunks:
            raise ValueError("鏂囨。鍐呭涓虹┖鎴栦笉鍙В鏋?)

        chunk_models: list[KnowledgeChunk] = []
        for idx, chunk in enumerate(chunks):
            embedding = await generate_embedding(chunk)
            chunk_models.append(
                KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=chunk,
                    token_count=estimate_tokens(chunk),
                    embedding=embedding,
                )
            )
        db.add_all(chunk_models)
        doc.chunk_count = len(chunk_models)
        doc.status = KnowledgeDocumentStatus.ready
    except Exception as exc:
        doc.status = KnowledgeDocumentStatus.failed
        doc.error_message = str(exc)

    await db.flush()
    return doc


async def list_documents(db: AsyncSession, *, limit: int = 100) -> list[KnowledgeDocument]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_document_by_id(db: AsyncSession, document_id: uuid.UUID) -> bool:
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        return False
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    await db.delete(doc)
    await db.flush()
    return True


async def search_knowledge(
    db: AsyncSession,
    *,
    query: str,
    top_k: int = 5,
) -> list[KnowledgeSearchResult]:
    embedding = await generate_embedding(query)

    stmt = (
        select(
            KnowledgeChunk.document_id,
            KnowledgeDocument.title,
            KnowledgeChunk.chunk_index,
            KnowledgeChunk.content,
            KnowledgeChunk.embedding.cosine_distance(embedding).label("distance"),
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.status == KnowledgeDocumentStatus.ready)
        .order_by("distance")
        .limit(top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        KnowledgeSearchResult(
            document_id=row.document_id,
            title=row.title,
            chunk_index=row.chunk_index,
            content=row.content,
            score=max(0.0, 1.0 - float(row.distance)),
        )
        for row in rows
    ]

