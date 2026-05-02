"""用户身份解析:(adapter_id, external_id) → user_id。

Phase 1 实现:复用 user_channel_bindings 表(扩展 platform 字段语义),
将 channel_runner._current_user_id() / channels/bindings.py 逻辑下沉至此。

Client Gateway 用 JWT 直出 user_id,**不调用此模块**。

参考: docs/ADR-001-multi-adapter-foundation.md §5
"""
from __future__ import annotations
from typing import Protocol


class IdentityResolver(Protocol):
    """身份解析协议。"""

    async def resolve(
        self, adapter_id: str, external_id: str, *, auto_bind: bool = True
    ) -> str:
        """解析 user_id;auto_bind=True 时为新外部用户自动创建 User 并绑定。

        当前 channels/bindings.py 中 resolve_user_id_with_fallback 的等价实现。
        """
        ...

    async def fallback_user_id(self) -> str | None:
        """单租户兜底:OPENAGENTIC_BOT_USER_ID env。"""
        ...
