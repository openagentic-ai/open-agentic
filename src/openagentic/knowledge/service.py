"""Knowledge base service layer."""

import uuid
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.knowledge.models import KnowledgeBase, Document, Chunk
from openagentic.knowledge.chunker import chunk_text
from openagentic.knowledge.embedder import embed_texts
from openagentic.knowledge.search import ensure_vector_indexes, similarity_search
from openagentic.knowledge.schemas import BatchDocumentUploadItem

logger = logging.getLogger(__name__)


async def create_knowledge_base(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    description: str | None = None,
    embedding_model: str = "nomic-embed-text",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> KnowledgeBase:
    """Create a new knowledge base."""
    kb = KnowledgeBase(
        user_id=user_id,
        name=name,
        description=description,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    db.add(kb)
    await db.flush()
    return kb


async def list_knowledge_bases(db: AsyncSession, user_id: uuid.UUID) -> list[KnowledgeBase]:
    """List all knowledge bases for a user."""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_base(
    db: AsyncSession, kb_id: uuid.UUID, user_id: uuid.UUID
) -> KnowledgeBase | None:
    """Get a knowledge base by ID, verifying ownership."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_knowledge_base(
    db: AsyncSession, kb_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a knowledge base and all its documents/chunks (via CASCADE)."""
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        return False
    await db.delete(kb)
    await db.flush()
    return True


async def add_document(
    db: AsyncSession,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content: str,
    content_type: str = "text/plain",
    parts: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Document:
    """Add a document to a knowledge base: chunk, embed, and store."""
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        raise ValueError("Knowledge base not found or access denied")

    merged_content = _merge_multimodal_content(content, parts)
    doc = Document(
        knowledge_base_id=kb_id,
        filename=filename,
        content_type=content_type,
        content=merged_content,
        status="processing",
    )
    db.add(doc)
    await db.flush()

    try:
        chunks = chunk_text(merged_content, chunk_size=kb.chunk_size, chunk_overlap=kb.chunk_overlap)

        if not chunks:
            doc.status = "completed"
            doc.chunk_count = 0
            await db.flush()
            return doc

        embeddings = await embed_texts(chunks, model=kb.embedding_model)

        for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                document_id=doc.id,
                knowledge_base_id=kb_id,
                content=chunk_content,
                chunk_index=i,
                embedding=embedding,
                metadata_={
                    "filename": filename,
                    "content_type": content_type,
                    "document_metadata": metadata or {},
                },
            )
            db.add(chunk)

        doc.status = "completed"
        doc.chunk_count = len(chunks)
        kb.document_count = kb.document_count + 1
        await db.flush()

    except Exception:
        doc.status = "failed"
        await db.flush()
        logger.exception("Failed to process document %s", doc.id)
        raise

    return doc


def _part_to_dict(part: Any) -> dict[str, Any]:
    if isinstance(part, dict):
        return part
    if hasattr(part, "model_dump"):
        return part.model_dump()
    return {}


def _merge_multimodal_content(content: str, parts: list[Any] | None) -> str:
    sections: list[str] = []
    if content and content.strip():
        sections.append(content.strip())

    for idx, raw_part in enumerate(parts or []):
        part = _part_to_dict(raw_part)
        p_type = str(part.get("type", "unknown"))
        p_name = str(part.get("name") or f"part-{idx + 1}")
        p_text = str(part.get("text") or "").strip()
        p_url = str(part.get("url") or "").strip()
        p_mime = str(part.get("mime_type") or "").strip()
        summary = f"[{p_type}] {p_name}"
        if p_mime:
            summary += f" ({p_mime})"
        if p_text:
            summary += f": {p_text}"
        elif p_url:
            summary += f": source={p_url}"
        sections.append(summary)

    merged = "\n\n".join(s for s in sections if s.strip())
    if not merged:
        raise ValueError("Document content and multimodal parts are both empty")
    return merged


async def add_documents_batch(
    db: AsyncSession,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    documents: list[dict[str, Any]],
    stop_on_error: bool = False,
) -> list[BatchDocumentUploadItem]:
    items: list[BatchDocumentUploadItem] = []
    for idx, payload in enumerate(documents):
        filename = str(payload.get("filename", f"document-{idx + 1}.txt"))
        try:
            doc = await add_document(
                db=db,
                kb_id=kb_id,
                user_id=user_id,
                filename=filename,
                content=str(payload.get("content", "")),
                content_type=str(payload.get("content_type", "text/plain")),
                parts=payload.get("parts"),
                metadata=payload.get("metadata"),
            )
            items.append(
                BatchDocumentUploadItem(
                    index=idx,
                    filename=filename,
                    status="completed",
                    document_id=str(doc.id),
                )
            )
        except Exception as exc:  # noqa: PERF203
            items.append(
                BatchDocumentUploadItem(
                    index=idx,
                    filename=filename,
                    status="failed",
                    error=str(exc),
                )
            )
            if stop_on_error:
                break
    return items


async def list_documents(
    db: AsyncSession, kb_id: uuid.UUID, user_id: uuid.UUID
) -> list[Document]:
    """List all documents in a knowledge base."""
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        raise ValueError("Knowledge base not found or access denied")

    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_document(
    db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a document and its chunks, update knowledge base count."""
    result = await db.execute(
        select(Document)
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .where(Document.id == doc_id, KnowledgeBase.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return False

    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id)
    )
    kb = kb_result.scalar_one_or_none()
    if kb and kb.document_count > 0:
        kb.document_count = kb.document_count - 1

    await db.delete(doc)
    await db.flush()
    return True


async def search(
    db: AsyncSession,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    rerank: bool = True,
    rerank_top_n: int = 20,
) -> list[dict]:
    """Search a knowledge base, verifying user ownership first."""
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        raise ValueError("Knowledge base not found or access denied")

    return await similarity_search(
        db=db,
        knowledge_base_id=kb_id,
        query=query,
        top_k=top_k,
        embedding_model=kb.embedding_model,
        rerank=rerank,
        rerank_top_n=rerank_top_n,
    )


async def optimize_index(
    db: AsyncSession,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[str]:
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        raise ValueError("Knowledge base not found or access denied")
    return await ensure_vector_indexes(db)
