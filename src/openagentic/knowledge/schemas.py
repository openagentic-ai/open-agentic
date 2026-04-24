"""模块说明（中文）：`src/openagentic/knowledge/schemas.py`。\n\n该文件定义请求/响应数据结构与校验规则。\n"""

import uuid
from datetime import datetime
from typing import Any, Optional

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
    content: str = ""
    content_type: str = "text/plain"
    parts: list["DocumentPart"] | None = None
    metadata: dict[str, Any] | None = None


class DocumentPart(BaseModel):
    type: str = Field(..., description="text/image/audio/video/table/file")
    text: str | None = None
    mime_type: str | None = None
    name: str | None = None
    url: str | None = None
    metadata: dict[str, Any] | None = None


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
    rerank: bool = True
    rerank_top_n: int = Field(default=20, ge=1, le=200)


class SearchResult(BaseModel):
    id: str
    content: str
    chunk_index: int
    document_id: str
    score: float
    rerank_score: float | None = None


class BatchDocumentUploadRequest(BaseModel):
    documents: list[DocumentUpload] = Field(default_factory=list, min_length=1, max_length=200)
    stop_on_error: bool = False


class BatchDocumentUploadItem(BaseModel):
    index: int
    filename: str
    status: str
    document_id: str | None = None
    error: str | None = None


class BatchDocumentUploadResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    items: list[BatchDocumentUploadItem]


class VectorIndexOptimizeResponse(BaseModel):
    applied: bool
    indexes: list[str]
