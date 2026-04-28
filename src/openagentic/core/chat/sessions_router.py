"""模块说明（中文）：`src/openagentic/core/chat/sessions_router.py`。

Sessions REST API —— 前端 SessionsPage 兼容层，映射到 Conversation 模型。
前端期望的字段名（name, state, createdAt 等）与 Conversation（title, 无 state 等）不同，
此层负责字段映射。
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.core.chat.models import Conversation
from openagentic.core.chat import service
from openagentic.db.session import get_db
from openagentic.deps import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: str
    name: str
    agentId: str | None = None
    channelId: str | None = None
    state: str = "active"
    createdAt: str
    messageCount: int = 0

    @classmethod
    def from_conv(cls, conv: Conversation) -> "SessionResponse":
        msg_count = len(conv.messages) if hasattr(conv, "messages") and conv.messages else 0
        return cls(
            id=str(conv.id),
            name=conv.title,
            state="active",
            createdAt=conv.created_at.isoformat() if isinstance(conv.created_at, datetime) else str(conv.created_at),
            messageCount=msg_count,
        )


class SessionCreateRequest(BaseModel):
    name: str = Field(default="New Session", max_length=255)
    agentId: str | None = None
    channelId: str | None = None


@router.get("")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户全部会话（前端 SessionsPage）。"""
    convs = await service.list_conversations(db, current_user.id)
    sessions = [SessionResponse.from_conv(c) for c in convs]
    return {"sessions": [s.model_dump() for s in sessions]}


@router.post("", status_code=201)
async def create_session(
    body: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新会话。"""
    conv = await service.create_conversation(db, current_user.id, body.name)
    return SessionResponse.from_conv(conv).model_dump()


@router.delete("/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话。"""
    deleted = await service.delete_conversation(db, session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": str(session_id)}
