"""OpenAgentic 共同底座 (Application Service Layer)。

L3 层职责:为所有 L4 接入(IM Adapter / Client Gateway)提供统一对话编排能力。

- ConversationOrchestrator: 流式事件协议入口
- Session / Identity / Intent / ToolRegistry: 跨端共享原语

设计原则:
- **零 adapter 知识** — 不 import 任何 extensions.adapters / gateway 模块
- **流式事件** — reply() 返回 AsyncIterator[ReplyEvent],各端自己渲染
- **不耦合传输协议** — 不知道 webhook / WebSocket / SDK 的存在

参考: docs/ADR-001-multi-adapter-foundation.md
"""
from __future__ import annotations

from openagentic.application.events import (
    ErrorEvent,
    EventType,
    FinalEvent,
    PartialEvent,
    ReplyEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from openagentic.application.identity import IdentityResolver
from openagentic.application.identity_default import DefaultIdentityResolver
from openagentic.application.orchestrator_default import DefaultOrchestrator
from openagentic.application.session import Session
from openagentic.application.session_store import DefaultSessionStore
from openagentic.application.tool_registry import ToolSpec
from openagentic.application.tool_registry_default import DefaultToolRegistry

__all__ = [
    # events
    "EventType", "ReplyEvent",
    "ThinkingEvent", "PartialEvent",
    "ToolCallEvent", "ToolResultEvent",
    "FinalEvent", "ErrorEvent",
    # session / store
    "Session", "DefaultSessionStore",
    # tool registry
    "ToolSpec", "DefaultToolRegistry",
    # identity
    "IdentityResolver", "DefaultIdentityResolver",
    # orchestrator
    "DefaultOrchestrator",
]
