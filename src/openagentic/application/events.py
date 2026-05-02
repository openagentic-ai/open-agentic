"""ReplyEvent 流式事件定义。

Orchestrator.reply() 返回 AsyncIterator[ReplyEvent]。各端按下表渲染:

| 事件        | 飞书           | 企微/钉钉 | Web/Android   |
|-------------|----------------|-----------|---------------|
| thinking    | 思考卡片占位    | 丢弃      | typing 指示    |
| partial     | 缓冲到 final   | 缓冲      | 实时渲染 token |
| tool_call   | 可选可视化      | 丢弃      | 工具调用卡片    |
| tool_result | 可选可视化      | 丢弃      | 工具结果卡片    |
| final       | 替换思考卡片    | 发文本    | 完整渲染        |
| error       | 错误卡片        | 发文本    | 错误提示        |

参考: docs/ADR-001-multi-adapter-foundation.md §2
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal


EventType = Literal["thinking", "partial", "tool_call", "tool_result", "final", "error"]


@dataclass(kw_only=True)
class ReplyEvent:
    """所有事件的基类(联合标签)。"""
    type: EventType
    session_id: str
    seq: int  # 单次 reply 流内单调递增,用于客户端去重/排序
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ThinkingEvent(ReplyEvent):
    """进度提示事件。"""
    type: EventType = "thinking"
    text: str = ""  # 简短描述当前 agent 在做什么(如 "正在检索知识库...")


@dataclass(kw_only=True)
class PartialEvent(ReplyEvent):
    """流式 token 片段。"""
    type: EventType = "partial"
    delta: str = ""  # 增量文本


@dataclass(kw_only=True)
class ToolCallEvent(ReplyEvent):
    """工具调用开始。"""
    type: EventType = "tool_call"
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""  # 关联 tool_result 的同步 ID


@dataclass(kw_only=True)
class ToolResultEvent(ReplyEvent):
    """工具调用返回。"""
    type: EventType = "tool_result"
    call_id: str = ""
    result: Any = None
    error: str | None = None


@dataclass(kw_only=True)
class FinalEvent(ReplyEvent):
    """终态完整回复(本次 reply 流的关闭事件)。"""
    type: EventType = "final"
    text: str = ""
    structured: dict[str, Any] | None = None  # 可选结构化输出(如卡片 JSON)


@dataclass(kw_only=True)
class ErrorEvent(ReplyEvent):
    """异常事件(也是流的关闭事件)。"""
    type: EventType = "error"
    code: str = ""  # 业务错误码,如 "rate_limited" / "auth_failed"
    message: str = ""


__all__ = [
    "EventType", "ReplyEvent",
    "ThinkingEvent", "PartialEvent",
    "ToolCallEvent", "ToolResultEvent",
    "FinalEvent", "ErrorEvent",
]
