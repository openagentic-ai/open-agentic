"""模块说明（中文）：`src/openagentic/knowledge/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

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
    """创建知识库配置（包含 embedding 模型和切块参数）。"""
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
    """列出用户的知识库，按创建时间倒序。"""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_base(
    db: AsyncSession, kb_id: uuid.UUID, user_id: uuid.UUID
) -> KnowledgeBase | None:
    """按 ID 查询知识库，并校验归属用户。"""
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
    """删除知识库（文档与分块通过级联一起删除）。"""
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
    """添加文档并完成“切块->向量化->入库”。

    若中间任一步骤异常：
    - 文档状态会标记为 failed；
    - 异常继续向上抛出，交给路由层转换为 HTTP 错误。
    """
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

        # 与配置的 embedding_model 对齐，确保检索向量空间一致。
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
        # 任何处理异常都标记 failed，避免“处理中”状态悬挂。
        doc.status = "failed"
        await db.flush()
        logger.exception("Failed to process document %s", doc.id)
        raise

    return doc


def _part_to_dict(part: Any) -> dict[str, Any]:
    """把多模态 part 统一转成 dict 结构，兼容 pydantic 模型输入。"""
    if isinstance(part, dict):
        return part
    if hasattr(part, "model_dump"):
        return part.model_dump()
    return {}


def _merge_multimodal_content(content: str, parts: list[Any] | None) -> str:
    """把文本和多模态部分合并为可索引的统一字符串。"""
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
    """批量导入文档。

    - 默认尽量继续处理后续条目；
    - `stop_on_error=True` 时遇错即停。
    """
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
    """列出知识库下所有文档。"""
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
    """删除文档并同步更新知识库文档计数。"""
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
    """执行知识库检索（先鉴权，再向量召回，可选重排序）。"""
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
    """触发向量索引优化（如 ivfflat/hnsw，取决于底层实现与数据库能力）。"""
    kb = await get_knowledge_base(db, kb_id, user_id)
    if not kb:
        raise ValueError("Knowledge base not found or access denied")
    return await ensure_vector_indexes(db)
