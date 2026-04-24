"""模块说明（中文）：`src/openagentic/core/chat/router.py`。\n\n该文件定义 HTTP 路由与请求入口，负责参数校验与服务层调用。\n"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.core.chat import schemas, service
from openagentic.db.session import get_db
from openagentic.deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["chat"])


@router.get("", response_model=list[schemas.ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_conversations(db, current_user.id)


@router.post("", response_model=schemas.ConversationResponse, status_code=201)
async def create_conversation(
    body: schemas.ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_conversation(
        db, current_user.id, body.title, body.model, body.system_prompt
    )


@router.get("/{conv_id}", response_model=schemas.ConversationResponse)
async def get_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await service.get_conversation(db, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await service.delete_conversation(db, conv_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/{conv_id}/messages", response_model=list[schemas.MessageResponse])
async def get_messages(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await service.get_conversation(db, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await service.get_messages(db, conv_id)


@router.post("/{conv_id}/messages")
async def send_message(
    conv_id: uuid.UUID,
    body: schemas.MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await service.get_conversation(db, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if body.stream:
        return StreamingResponse(
            service.send_message_stream(db, conv, body.message, body.model),
            media_type="text/event-stream",
        )
    else:
        msg = await service.send_message(db, conv, body.message, body.model)
        return schemas.MessageResponse.model_validate(msg)
