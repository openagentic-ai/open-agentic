"""模块说明（中文）：`src/openagentic/channels/router.py`。

Channels 管理 REST API —— 渠道实例 CRUD（前端 ChannelsPage）。
与 extensions/channels/router.py（webhook 路由）职责分离。
"""

from __future__ import annotations

import uuid
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.channels.models import ChannelConfig
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.deps import get_current_user

router = APIRouter(prefix="/api/channels", tags=["channels-management"])


class ChannelResponse(BaseModel):
    id: str
    type: str
    name: str
    enabled: bool
    config: dict | None = None

    @classmethod
    def from_model(cls, c: ChannelConfig) -> "ChannelResponse":
        config_dict = None
        if c.config:
            try:
                config_dict = json.loads(c.config)
            except json.JSONDecodeError:
                config_dict = {}
        return cls(
            id=str(c.id),
            type=c.type,
            name=c.name,
            enabled=c.enabled,
            config=config_dict,
        )


class ChannelCreateRequest(BaseModel):
    type: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    enabled: bool = True
    config: dict | None = None


class ChannelUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict | None = None


@router.get("")
async def list_channels(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户配置的全部渠道。"""
    result = await db.execute(
        select(ChannelConfig)
        .where(ChannelConfig.user_id == user.id)
        .order_by(ChannelConfig.created_at.desc())
    )
    channels = result.scalars().all()
    return {"channels": [ChannelResponse.from_model(c).model_dump() for c in channels]}


@router.post("", status_code=201)
async def create_channel(
    body: ChannelCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建渠道配置。"""
    cfg = ChannelConfig(
        user_id=user.id,
        type=body.type,
        name=body.name,
        enabled=body.enabled,
        config=json.dumps(body.config) if body.config else None,
    )
    db.add(cfg)
    await db.flush()
    return ChannelResponse.from_model(cfg).model_dump()


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除渠道配置。"""
    result = await db.execute(
        select(ChannelConfig).where(
            ChannelConfig.id == channel_id,
            ChannelConfig.user_id == user.id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(cfg)
    await db.flush()
    return {"deleted": str(channel_id)}
