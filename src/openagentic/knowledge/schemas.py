"""Knowledge module Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    embedding_model: str = "nomic-embed-text"
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    document_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpload(BaseModel):
    filename: str = Field(..., max_length=500)
    content: str
    content_type: str = "text/plain"


class DocumentResponse(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    content_type: str
    chunk_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    id: str
    content: str
    chunk_index: int
    document_id: str
    score: float
