"""模块说明（中文）：`src/openagentic/channels/bindings.py`。

外部渠道账号 → OpenAgentic User 的解析服务。

调用方（如 channel_runner 的 workflow 工具）按 (platform, external_id) 反查；
未命中且配置了 OPENAGENTIC_BOT_USER_ID 时，env 作为单租户兜底——
方便老部署在迁移到映射表期间不中断。
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from sqlalchemy import select

from openagentic.channels.models import UserChannelBinding
from openagentic.db.session import async_session


async def resolve_user_id(platform: str, external_id: str) -> Optional[uuid.UUID]:
    """按 (platform, external_id) 反查 OpenAgentic User UUID。

    返回 None 表示未绑定——调用方负责兜底（env、引导绑定流程等）。
    """
    if not platform or not external_id:
        return None
    async with async_session() as db:
        stmt = select(UserChannelBinding.user_id).where(
            UserChannelBinding.platform == platform,
            UserChannelBinding.external_id == external_id,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
    return row


def fallback_bot_user_id() -> Optional[uuid.UUID]:
    """env OPENAGENTIC_BOT_USER_ID 兜底，未配置或非法返回 None。"""
    raw = os.getenv("OPENAGENTIC_BOT_USER_ID", "").strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        return None


async def resolve_user_id_with_fallback(
    platform: str, external_id: str
) -> Optional[uuid.UUID]:
    """先查映射表，再走 env 兜底。"""
    uid = await resolve_user_id(platform, external_id)
    if uid is not None:
        return uid
    return fallback_bot_user_id()
