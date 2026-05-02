"""DefaultIdentityResolver——IdentityResolver 协议的默认实现。

Phase 1 策略: **薄包层**。底层逻辑暂留在 channels/bindings.py
(resolve_user_id / auto_bind_feishu_user / fallback_bot_user_id),
本类负责:
- 概念翻译: adapter_id ↔ platform(同义,直接传透)
- 类型翻译: UUID → str(Protocol 要求 str)
- 行为收敛: resolve_user_id_with_fallback 已经包了"查 → 自动绑 → fallback"

物理迁移到 application/ 留待 P0-2 飞书迁底座那次手术,届时
channels/bindings.py 改成 re-export 兼容层。

Client Gateway 用 JWT 直出 user_id,**不调用此类**。

参考: docs/ADR-001-multi-adapter-foundation.md §5
"""
from __future__ import annotations

import structlog

from openagentic.application.identity import IdentityResolver  # noqa: F401

logger = structlog.get_logger("openagentic.application.identity")


class DefaultIdentityResolver:
    """薄包层:转发到 channels.bindings 现有逻辑。"""

    async def resolve(
        self, adapter_id: str, external_id: str, *, auto_bind: bool = True
    ) -> str | None:
        if not adapter_id or not external_id:
            return None

        # 延迟 import 避开 application <-> channels 启动期循环
        from openagentic.channels.bindings import (
            resolve_user_id,
            auto_bind_feishu_user,
            fallback_bot_user_id,
        )

        uid = await resolve_user_id(adapter_id, external_id)
        if uid is not None:
            return str(uid)

        if auto_bind and adapter_id == "feishu":
            uid = await auto_bind_feishu_user(
                sender_id=external_id,
                sender_open_id=external_id,
            )
            if uid is not None:
                return str(uid)

        fb = fallback_bot_user_id()
        return str(fb) if fb is not None else None

    async def fallback_user_id(self) -> str | None:
        from openagentic.channels.bindings import fallback_bot_user_id
        fb = fallback_bot_user_id()
        return str(fb) if fb is not None else None


__all__ = ["DefaultIdentityResolver"]
