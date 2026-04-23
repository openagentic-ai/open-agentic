"""Knowledge base API routes for Phase 4 MVP."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.db.session import get_db
from openagentic.knowledge import schemas, service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/documents/upload", response_model=schemas.KnowledgeDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="涓婁紶鏂囦欢涓虹┖")
    doc = await service.ingest_document(
        db,
        filename=file.filename or "untitled.txt",
        content_type=file.content_type or "text/plain",
        data=raw,
        title=title,
        user_id=None,
    )
    return doc


@router.get("/documents", response_model=list[schemas.KnowledgeDocumentResponse])
async def list_documents(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_documents(db, limit=limit)


@router.delete("/documents/{document_id}")
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await service.delete_document_by_id(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="鏂囨。涓嶅瓨鍦?)
    return {"ok": True}


@router.post("/search", response_model=schemas.KnowledgeSearchResponse)
async def search(payload: schemas.KnowledgeSearchRequest, db: AsyncSession = Depends(get_db)):
    results = await service.search_knowledge(db, query=payload.query, top_k=payload.top_k)
    return schemas.KnowledgeSearchResponse(results=results)

