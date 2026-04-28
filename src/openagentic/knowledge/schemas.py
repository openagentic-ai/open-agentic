"""模块说明（中文）：`src/openagentic/knowledge/schemas.py`。

知识库/RAG 模块请求/响应数据结构。
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求：名称、embedding 模型、分块参数。"""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    embedding_model: str = "nomic-embed-text"
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class KnowledgeBaseResponse(BaseModel):
    """知识库查询响应（含文档计数）。"""
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


class DocumentPart(BaseModel):
    """多模态文档片段：text/image/audio/video/table/file。"""
    type: str = Field(..., description="text/image/audio/video/table/file")
    text: str | None = None
    mime_type: str | None = None
    name: str | None = None
    url: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentUpload(BaseModel):
    """文档上传请求：文本内容 + 可选多模态 parts。"""
    filename: str = Field(..., max_length=500)
    content: str = ""
    content_type: str = "text/plain"
    parts: list[DocumentPart] | None = None
    metadata: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    """文档查询响应。"""
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    content_type: str
    chunk_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """向量检索请求：query + top_k + 可选重排序。"""
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    rerank: bool = True
    rerank_top_n: int = Field(default=20, ge=1, le=200)


class SearchResult(BaseModel):
    """检索结果条目。"""
    id: str
    content: str
    chunk_index: int
    document_id: str
    score: float
    rerank_score: float | None = None


class BatchDocumentUploadRequest(BaseModel):
    """批量文档上传请求：1-200 条，可选遇错即停。"""
    documents: list[DocumentUpload] = Field(default_factory=list, min_length=1, max_length=200)
    stop_on_error: bool = False


class BatchDocumentUploadItem(BaseModel):
    """批量上传单条结果。"""
    index: int
    filename: str
    status: str
    document_id: str | None = None
    error: str | None = None


class BatchDocumentUploadResponse(BaseModel):
    """批量上传汇总响应。"""
    total: int
    succeeded: int
    failed: int
    items: list[BatchDocumentUploadItem]


class VectorIndexOptimizeResponse(BaseModel):
    """向量索引优化响应。"""
    applied: bool
    indexes: list[str]


class KnowledgeDocumentResponse(BaseModel):
    """前端兼容的文档响应（KnowledgeBasePage 期望的字段名）。"""
    id: str
    user_id: str | None = None
    title: str
    filename: str
    content_type: str
    size_bytes: int = 0
    status: str
    error_message: str | None = None
    chunk_count: int = 0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | str
    updated_at: datetime | str | None = None
