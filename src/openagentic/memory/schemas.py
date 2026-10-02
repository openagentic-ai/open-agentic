"""Pydantic schemas for /api/memory/ REST API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

CoreCategory = Literal["user_profile", "project_fact", "preference", "reference"]

# -- Core Memory -----------------------------------------------------------

class CoreMemoryCreate(BaseModel):
    key: str = Field(..., max_length=128, description="记忆键名（唯一标识）")
    value: str = Field(..., description="记忆内容（Markdown）")
    category: str = Field(
        "reference",
        description="分类：user_profile / project_fact / preference / reference",
    )
    importance: float = Field(0.5, ge=0.0, le=1.0, description="重要性 0~1")


class CoreMemoryResponse(BaseModel):
    key: str
    value: str
    category: str
    importance: float
    created: str
    updated: str
    file_path: str


# -- Episodic Memory -------------------------------------------------------

class EpisodeCreate(BaseModel):
    title: str = Field(..., max_length=128, description="情节标题")
    summary: str = Field(..., description="对话/任务摘要")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class EpisodeResponse(BaseModel):
    title: str
    summary: str
    file: str


# -- Procedural Memory -----------------------------------------------------

class ProcedureCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}

    name: str = Field(..., min_length=1, max_length=128, description="步骤名称")
    description: str = Field(..., max_length=3000, description="步骤描述")
    trigger_pattern: str = Field("", max_length=200, description="触发条件关键词")
    steps: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(
        ..., min_length=1, max_length=100, description="步骤列表",
    )


class ProcedureResponse(BaseModel):
    name: str
    content: str
    file: str


# -- Search ----------------------------------------------------------------

class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description="搜索关键词")
    top_k: int = Field(10, ge=1, le=50, description="返回条数")
