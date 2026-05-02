"""客户端 WebSocket endpoint——ReplyEvent 流推送。

端点(Phase 3 实现):
- WS /ws?token=<jwt>&session_id=<sid>

握手:
1. 客户端连接,query 带 JWT + session_id
2. 服务端验 JWT → user_id;查 session 归属;不匹配则关闭
3. 进入消息循环

消息协议(JSON 行):
- 客户端 → 服务端:
  { "type": "user_message", "text": "...", "client_msg_id": "..." }
  { "type": "intent", "name": "list_workflows", "params": {} }       # 替代 IM 文本快路径
  { "type": "ping" }
- 服务端 → 客户端: ReplyEvent dataclass 序列化(见 application/events.py)
  + { "type": "pong" }

每条 user_message 触发一次 Orchestrator.reply() 流,事件依次推送至 final/error 关闭流(同一 session 可发下一条)。

参考: docs/ADR-001-multi-adapter-foundation.md §2, §4
"""
from __future__ import annotations
from fastapi import APIRouter

# Phase 0 仅占位
ws_router = APIRouter(tags=["client-gateway-ws"])
