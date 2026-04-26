"""模块说明（中文）：`src/openagentic/agent/schemas.py`。

Agent 模块请求/响应数据结构（Pydantic models）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentCreate(BaseModel):
    """创建 Agent 请求体。tools 为空时默认启用全部内置工具。"""
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: dict[str, Any] | None = None


class AgentUpdate(BaseModel):
    """更新 Agent 请求体（所有字段可选，仅传入字段生效）。"""
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    """Agent 查询响应（from_attributes=True 支持 ORM 自动转换）。"""
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str | None
    model: str | None
    tools: list[str] | None
    config: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunRequest(BaseModel):
    """执行 Agent 请求体。"""
    input: str


class ExecutionResponse(BaseModel):
    """Agent 执行记录响应。"""
    id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    input: str
    output: str | None
    steps: list[dict[str, Any]] | None
    token_total: int | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ToolInfo(BaseModel):
    """工具信息（名称 + 描述 + 参数 schema）。"""
    name: str
    description: str
    parameters: dict[str, Any]
