"""Session 抽象——跨端会话的统一标识。

替代旧 channel_runner.py 中裸字符串 chat_id。

Session 是 (adapter_id, external_session_id, user_id) 的语义封装:
- IM: external_session_id = 飞书 chat_id / 企微会话 ID
- Client(Web/Android): external_session_id = 客户端创建的 session UUID
- 跨端连续性: 多个 Session 可关联到同一 user_id 的"逻辑对话"(Phase 4+ 实现)

参考: docs/ADR-001-multi-adapter-foundation.md §1, §5
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Session:
    """跨端会话标识。"""
    session_id: str            # 内部 UUID(底座生成)
    adapter_id: str            # "feishu" | "wecom" | "dingtalk" | "web" | "android" | ...
    external_session_id: str   # 各端原生会话 ID(飞书 chat_id / 客户端 UUID)
    user_id: str               # 已解析的内部用户 ID
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionStore(Protocol):
    """会话存储接口。Phase 1 决定实现(内存 / DB)。"""

    async def get_or_create(
        self, adapter_id: str, external_session_id: str, user_id: str
    ) -> Session:
        """按 (adapter_id, external_session_id) 查询;不存在则创建。"""
        ...

    async def get_by_id(self, session_id: str) -> Session | None: ...

    async def list_by_user(self, user_id: str) -> list[Session]: ...
