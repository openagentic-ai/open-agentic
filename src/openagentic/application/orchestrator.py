"""ConversationOrchestrator——底座对话编排核心。

L4(IM Adapter / Client Gateway)调用 reply(session, user_text),
拿到 AsyncIterator[ReplyEvent] 流,自行决定渲染。

内部职责:
1. 注入记忆(MemoryManager)
2. 拼装可见工具集(ToolRegistry.list_for(adapter_id))
3. Intent 快路径优先(IntentRouter.dispatch)
4. 走 ConversationEngine 工具循环
5. 把工具循环过程透传成 ReplyEvent 流

不知道:
- webhook / WebSocket / SDK
- 卡片 / 富文本 / 平台特化 UI
- 用户身份解析(由调用方传入已解析的 user_id)

参考: docs/ADR-001-multi-adapter-foundation.md §1, §2
"""
from __future__ import annotations
from typing import AsyncIterator, Protocol

from openagentic.application.events import ReplyEvent
from openagentic.application.session import Session


class ConversationOrchestrator(Protocol):
    """对话编排协议。Phase 1 实现 DefaultOrchestrator。"""

    async def reply(self, session: Session, user_text: str) -> AsyncIterator[ReplyEvent]:
        """流式回复。

        实现要点(Phase 1):
        - 第一帧总是 ThinkingEvent("收到,开始处理")
        - LLM 流式调用 → PartialEvent
        - 工具调用 → ToolCallEvent + ToolResultEvent
        - 终态 → FinalEvent(必发,流的关闭)
        - 异常 → ErrorEvent(替代 FinalEvent 关闭流)
        """
        ...
