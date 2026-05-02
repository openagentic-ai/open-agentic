"""工具注册分级。

两类:
- **通用工具**: run_command / read_file / save_memory / 8 个 workflow 工具 — 底座默认注入
- **adapter 贡献工具**: lark_cli / 企微 OA / 钉钉 OA — adapter.start() 时贡献,仅在该 adapter 会话上下文可见

Orchestrator 在构造 ConversationEngine 时按 session.adapter_id 拼出本次可见工具集。

参考: docs/ADR-001-multi-adapter-foundation.md §7
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol


ToolHandler = Callable[..., Awaitable[Any]]


@dataclass
class ToolSpec:
    """工具元信息(对齐 LiteLLM tools schema)。"""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


class ToolRegistry(Protocol):
    """工具注册表。"""

    def register_global(self, spec: ToolSpec) -> None:
        """注册通用工具(全 adapter 可见)。"""
        ...

    def register_adapter_tool(self, adapter_id: str, spec: ToolSpec) -> None:
        """注册 adapter 贡献工具(仅该 adapter 会话可见)。"""
        ...

    def list_for(self, adapter_id: str) -> list[ToolSpec]:
        """列出指定 adapter 会话的可见工具(global + adapter)。"""
        ...

    def get(self, name: str) -> ToolSpec | None: ...
