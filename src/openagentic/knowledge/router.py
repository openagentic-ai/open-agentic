"""模块说明（中文）：`src/openagentic/knowledge/router.py`。\n\n该文件定义 HTTP 路由与请求入口，负责参数校验与服务层调用。\n"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.core.auth.models import User
from openagentic.knowledge import service
from openagentic.knowledge.schemas import (
    BatchDocumentUploadRequest,
    BatchDocumentUploadResponse,
    DocumentResponse,
    DocumentUpload,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeDocumentResponse,
    SearchRequest,
    SearchResult,
    VectorIndexOptimizeResponse,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _item_status(item) -> str:
    if isinstance(item, dict):
        return str(item.get("status", ""))
    return str(getattr(item, "status", ""))


@router.get("/", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all knowledge bases for the current user."""
    return await service.list_knowledge_bases(db, user.id)


@router.post("/", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base."""
    return await service.create_knowledge_base(
        db=db,
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        embedding_model=payload.embedding_model,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a knowledge base by ID."""
    kb = await service.get_knowledge_base(db, kb_id, user.id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge base and all its documents."""
    deleted = await service.delete_knowledge_base(db, kb_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")


@router.post("/{kb_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def add_document(
    kb_id: uuid.UUID,
    payload: DocumentUpload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a document to a knowledge base (text content via JSON)."""
    try:
        return await service.add_document(
            db=db,
            kb_id=kb_id,
            user_id=user.id,
            filename=payload.filename,
            content=payload.content,
            content_type=payload.content_type,
            parts=payload.parts,
            metadata=payload.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{kb_id}/documents/batch",
    response_model=BatchDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_documents_batch(
    kb_id: uuid.UUID,
    payload: BatchDocumentUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        items = await service.add_documents_batch(
            db=db,
            kb_id=kb_id,
            user_id=user.id,
            documents=[doc.model_dump() for doc in payload.documents],
            stop_on_error=payload.stop_on_error,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    succeeded = sum(1 for item in items if _item_status(item) == "completed")
    failed = len(items) - succeeded
    return BatchDocumentUploadResponse(
        total=len(items),
        succeeded=succeeded,
        failed=failed,
        items=items,
    )


@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents in a knowledge base."""
    try:
        return await service.list_documents(db, kb_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks."""
    deleted = await service.delete_document(db, doc_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post("/{kb_id}/search", response_model=list[SearchResult])
async def search_knowledge_base(
    kb_id: uuid.UUID,
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search a knowledge base using vector similarity."""
    try:
        return await service.search(
            db=db,
            kb_id=kb_id,
            user_id=user.id,
            query=payload.query,
            top_k=payload.top_k,
            rerank=payload.rerank,
            rerank_top_n=payload.rerank_top_n,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{kb_id}/optimize-index", response_model=VectorIndexOptimizeResponse)
async def optimize_vector_index(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        indexes = await service.optimize_index(db=db, kb_id=kb_id, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return VectorIndexOptimizeResponse(applied=bool(indexes), indexes=indexes)


# -- 前端 KnowledgeBasePage 兼容端点 -------------------------------------


@router.post("/documents/upload", response_model=KnowledgeDocumentResponse)
async def upload_document_multipart(
    file: UploadFile = File(...),
    title: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档（multipart/form-data），自动使用用户默认知识库。

    前端 KnowledgeBasePage 通过 FormData 发送 file + title，
    此端点读取文件内容，写入默认 KB，返回前端期望的字段。
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("latin-1")

    kb = await service.get_or_create_default_kb(db, user.id)
    doc = await service.add_document(
        db=db,
        kb_id=kb.id,
        user_id=user.id,
        filename=file.filename,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )
    return KnowledgeDocumentResponse(
        id=str(doc.id),
        user_id=str(user.id),
        title=title or file.filename,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content_bytes),
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        updated_at=getattr(doc, "updated_at", None),
    )


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
async def list_all_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    """列出用户所有知识库的全部文档（前端简洁接口，无需指定 kb_id）。"""
    all_docs: list[KnowledgeDocumentResponse] = []
    kbs = await service.list_knowledge_bases(db, user.id)
    for kb in kbs:
        docs = await service.list_documents(db, kb.id, user.id)
        for doc in docs:
            all_docs.append(KnowledgeDocumentResponse(
                id=str(doc.id),
                user_id=str(user.id),
                title=doc.filename,
                filename=doc.filename,
                content_type=doc.content_type,
                status=doc.status,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at,
                updated_at=getattr(doc, "updated_at", None),
            ))
        if len(all_docs) >= limit:
            break
    return all_docs[:limit]


@router.delete("/documents/{doc_id}", response_model=dict)
async def delete_document_flat(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档（前端简洁接口，无需 kb_id）。"""
    deleted = await service.delete_document(db, doc_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"ok": True}


@router.post("/search", response_model=dict)
async def search_all_knowledge(
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """跨所有知识库检索（前端简洁接口，无需 kb_id）。

    返回格式匹配前端 KnowledgeSearchResponse：{ results: [...] }
    """
    all_results: list[dict] = []
    kbs = await service.list_knowledge_bases(db, user.id)
    for kb in kbs:
        try:
            results = await service.search(
                db=db, kb_id=kb.id, user_id=user.id,
                query=payload.query, top_k=payload.top_k,
                rerank=payload.rerank, rerank_top_n=payload.rerank_top_n,
            )
            all_results.extend(results)
        except ValueError:
            continue
    # 按 score 降序
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    top = all_results[:payload.top_k]
    return {
        "results": [
            {
                "document_id": r.get("document_id", ""),
                "title": r.get("content", "")[:80],
                "chunk_index": r.get("chunk_index", 0),
                "content": r.get("content", ""),
                "score": r.get("score", 0),
            }
            for r in top
        ]
    }
