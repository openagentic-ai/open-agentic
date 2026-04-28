"""模块说明（中文）：`src/openagentic/channels/bindings.py`。

外部渠道账号 → OpenAgentic User 的解析服务。

调用方（如 channel_runner 的 workflow 工具）按 (platform, external_id) 反查；
未命中时自动触发绑定——从渠道侧获取用户信息，匹配或创建 OA User 并写入映射表。
"""

from __future__ import annotations

import os
import uuid
import structlog
from typing import Optional

from sqlalchemy import select

from openagentic.channels.models import UserChannelBinding
from openagentic.db.session import async_session

logger = structlog.get_logger("openagentic.channels.bindings")


async def resolve_user_id(platform: str, external_id: str) -> Optional[uuid.UUID]:
    """按 (platform, external_id) 反查 OpenAgentic User UUID。

    返回 None 表示未绑定——调用方应引导自动绑定或提示用户去控制台绑定。
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


async def auto_bind_feishu_user(
    sender_id: str,
    sender_open_id: str,
    sender_name: str = "",
) -> Optional[uuid.UUID]:
    """自动绑定飞书用户：获取用户信息 → 匹配或创建 OA User → 写入映射表。

    Args:
        sender_id: 飞书 user_id
        sender_open_id: 飞书 open_id（优先用作 external_id）
        sender_name: 飞书发送者显示名（如果 SDK 已提供）

    Returns:
        绑定后的 OA User UUID，失败返回 None。
    """
    if not sender_open_id and not sender_id:
        return None

    external_id = sender_open_id or sender_id
    display_name = sender_name or f"飞书用户_{external_id[:8]}"

    # 尝试从飞书 API 获取用户真实姓名（企业通讯录权限）
    real_name = await _feishu_lookup_name(external_id)
    if real_name:
        display_name = real_name

    try:
        from openagentic.core.auth.models import User
        async with async_session() as db:
            # 用 default_domain 邮箱查找已有用户
            email = f"feishu_{external_id[:12]}@openagentic.local"
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                # 创建新用户
                import secrets
                user = User(
                    email=email,
                    hashed_password="feishu-auto:" + secrets.token_urlsafe(32),
                    display_name=display_name,
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                logger.info("auto-created user", email=email, user_id=str(user.id))

            # 创建绑定
            existing = await db.execute(
                select(UserChannelBinding).where(
                    UserChannelBinding.platform == "feishu",
                    UserChannelBinding.external_id == external_id,
                )
            )
            if not existing.scalar_one_or_none():
                binding = UserChannelBinding(
                    user_id=user.id,
                    platform="feishu",
                    external_id=external_id,
                    display_name=display_name,
                )
                db.add(binding)
                await db.commit()
                logger.info("auto-bound feishu user", external_id=external_id, user_id=str(user.id))
            return user.id
    except Exception:
        logger.exception("auto_bind_feishu_user failed")
        return None


async def _feishu_lookup_name(external_id: str) -> str:
    """通过飞书通讯录 API 查询用户真实姓名。

    需要 app 具备 contact:user:readonly 权限。
    """
    try:
        import httpx
        app_id = os.getenv("FEISHU_APP_ID", "")
        app_secret = os.getenv("FEISHU_APP_SECRET", "")
        if not app_id or not app_secret:
            return ""

        # 获取 tenant_access_token
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            token_data = token_resp.json()
            token = token_data.get("tenant_access_token", "")
            if not token or token_resp.status_code != 200:
                return ""

            # 查用户信息（用 open_id 查通讯录）
            user_resp = await client.get(
                f"https://open.feishu.cn/open-apis/contact/v3/users/{external_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"user_id_type": "open_id"},
            )
            if user_resp.status_code == 200:
                user_data = user_resp.json()
                user_info = user_data.get("data", {}).get("user", {})
                name = user_info.get("name", "")
                return name
    except Exception:
        pass
    return ""


async def resolve_user_id_with_fallback(
    platform: str, external_id: str
) -> Optional[uuid.UUID]:
    """先查映射表 → 自动绑定 → env 兜底。"""
    uid = await resolve_user_id(platform, external_id)
    if uid is not None:
        return uid

    # 飞书渠道自动绑定
    if platform == "feishu":
        uid = await auto_bind_feishu_user(
            sender_id=external_id,
            sender_open_id=external_id,
        )
        if uid is not None:
            return uid

    return fallback_bot_user_id()
