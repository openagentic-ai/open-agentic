"""模块说明（中文）：`src/openagentic/core/chat/schemas.py`。\n\n该文件定义请求/响应数据结构与校验规则。\n"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    model: str | None = None
    system_prompt: str | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    model: str | None
    system_prompt: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None
    stream: bool = True


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    model: str | None
    token_count_input: int | None
    token_count_output: int | None
    cost_usd: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatStreamEvent(BaseModel):
    """SSE event for streaming chat."""
    event: str  # "token", "done", "error"
    data: str
