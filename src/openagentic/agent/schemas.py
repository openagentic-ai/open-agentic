"""模块说明（中文）：`src/openagentic/agent/schemas.py`。\n\n该文件定义请求/响应数据结构与校验规则。\n"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: dict[str, Any] | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
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
    input: str


class ExecutionResponse(BaseModel):
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
    name: str
    description: str
    parameters: dict[str, Any]
