"""客户端会话 REST API。

端点(Phase 3 实现):
- POST /api/client/sessions        创建会话
- GET  /api/client/sessions        列出当前用户的会话
- GET  /api/client/sessions/{id}/messages   会话消息历史
- POST /api/client/sessions/{id}/messages   发送消息(同步返回 final;流式见 /ws)
- DELETE /api/client/sessions/{id}          结束会话

所有端点要求 JWT 鉴权,user_id 从 JWT 直出。

不做的事:
- 不做 workflow/knowledge/skill 的 CRUD——那些走 src/openagentic/workflow/router.py 等已有路由
- 不做 webhook 解密——那是 extensions/adapters/ 的事

参考: docs/ADR-001-multi-adapter-foundation.md §4
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.core.chat import schemas, service
from openagentic.db.session import get_db
from openagentic.deps import get_current_user

router = APIRouter(prefix="/api/client", tags=["client-gateway"])

@router.get("/sessions", response_model=list[schemas.ConversationResponse])
async def list_sessions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.list_conversations(db, current_user.id)


@router.post("/sessions", response_model=schemas.ConversationResponse, status_code=201)
async def create_session(body: schemas.ConversationCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.create_conversation(db, current_user.id, body.title, body.model, body.system_prompt)


@router.get("/sessions/{session_id}/messages", response_model=list[schemas.MessageResponse])
async def list_session_messages(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conversation = await service.get_conversation(db, session_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")
    return await service.get_messages(db, session_id)


@router.post("/sessions/{session_id}/messages", response_model=schemas.MessageResponse)
async def send_session_message(session_id: uuid.UUID, body: schemas.MessageCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conversation = await service.get_conversation(db, session_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")
    if body.stream:
        raise HTTPException(status_code=400, detail="Use the WebSocket endpoint for streaming")
    return await service.send_message(db, conversation, body.message, body.model)
