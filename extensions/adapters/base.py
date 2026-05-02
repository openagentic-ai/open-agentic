"""Adapter Protocol——替代 channels/base.py 的 Channel ABC。

不强制 webhook / CLI / 消息格式 / 传输协议。每个 adapter 自己决定:
- 飞书: lark-oapi WebSocket 长连接
- 企微: FastAPI webhook + AES 解密
- 钉钉: 钉钉 OpenSDK / webhook(待 Phase 待启)

接入底座的最小契约:
1. 启动时拿到 ConversationOrchestrator,即可调 reply() 流
2. 启动时可选向 ToolRegistry.register_adapter_tool() 贡献本端独有工具(如飞书 lark_cli)
3. 自行处理 ReplyEvent → 平台原生消息的渲染

参考: docs/ADR-001-multi-adapter-foundation.md §3
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from openagentic.application.orchestrator import ConversationOrchestrator


@runtime_checkable
class Adapter(Protocol):
    """所有 IM adapter 必须实现的最小协议。"""

    adapter_id: str  # "feishu" | "wecom" | "dingtalk" | ...

    async def start(self, orchestrator: ConversationOrchestrator) -> None:
        """启动 adapter(连 WS / 注册 webhook / 起后台任务)。

        实现要求:
        - 拿到 orchestrator 后,后续每条入站消息走 orchestrator.reply()
        - 可选向 orchestrator 拿到的 tool_registry 贡献本端独有工具
        - 启动失败应抛异常,registry 会捕获并仅日志警告(隔离)
        """
        ...

    async def stop(self) -> None:
        """停止 adapter,释放资源。"""
        ...
