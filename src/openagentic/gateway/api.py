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
from fastapi import APIRouter

# Phase 0 仅占位
router = APIRouter(prefix="/api/client", tags=["client-gateway"])
