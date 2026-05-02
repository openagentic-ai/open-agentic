"""Client Gateway——Web/Android/iOS/桌面客户端的统一入口。

提供:
- REST API (api.py): 客户端会话 CRUD、消息发送
- WebSocket (ws.py): ReplyEvent 流推送

与 IM Adapter 的区别:
- 鉴权: JWT(复用 core/auth/),不做平台 open_id 解析
- 协议: HTTP/WS,不做 webhook/SDK 长连接
- 用户: 直接拿 JWT 的 user_id,不走 IdentityResolver

参考: docs/ADR-001-multi-adapter-foundation.md §4
"""
from __future__ import annotations
__all__: list[str] = []
