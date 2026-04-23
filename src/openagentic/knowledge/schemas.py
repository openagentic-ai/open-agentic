"""Pydantic schemas for knowledge base APIs."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from openagentic.knowledge.models import KnowledgeDocumentStatus


class KnowledgeDocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    title: str
    filename: str
    content_type: str
    size_bytes: int
    status: KnowledgeDocumentStatus
    error_message: str | None
    chunk_count: int
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    document_id: uuid.UUID
    title: str
    chunk_index: int
    content: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult]

