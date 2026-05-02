"""DefaultToolRegistry——ToolRegistry 默认实现。

两类工具:
- global: 所有 adapter 会话可见(workflow / memory / system 工具)
- adapter-scoped: 仅指定 adapter_id 会话可见(如飞书 lark_cli)

list_for(adapter_id) 拼装顺序: global → adapter(后注册的同名覆盖)。

参考: docs/ADR-001-multi-adapter-foundation.md §7
"""
from __future__ import annotations

from openagentic.application.tool_registry import ToolSpec


class DefaultToolRegistry:
    """内存版 ToolRegistry。无锁——register_* 期望在启动期完成,run-time 只读。"""

    def __init__(self) -> None:
        self._global: dict[str, ToolSpec] = {}
        self._per_adapter: dict[str, dict[str, ToolSpec]] = {}   # adapter_id -> {name: spec}

    def register_global(self, spec: ToolSpec) -> None:
        self._global[spec.name] = spec

    def register_adapter_tool(self, adapter_id: str, spec: ToolSpec) -> None:
        self._per_adapter.setdefault(adapter_id, {})[spec.name] = spec

    def list_for(self, adapter_id: str) -> list[ToolSpec]:
        merged: dict[str, ToolSpec] = dict(self._global)
        merged.update(self._per_adapter.get(adapter_id, {}))
        return list(merged.values())

    def get(self, name: str) -> ToolSpec | None:
        # 全表检索:先 global,再各 adapter(用于 executor 跨域查找)
        spec = self._global.get(name)
        if spec is not None:
            return spec
        for tools in self._per_adapter.values():
            if name in tools:
                return tools[name]
        return None

    # ── 便捷封装:转 LiteLLM tools schema ─────────────────────────────────

    def litellm_schema_for(self, adapter_id: str) -> list[dict]:
        """返回适配器可见工具的 LiteLLM tools schema 列表(供 ConversationEngine.tools)。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                },
            }
            for s in self.list_for(adapter_id)
        ]


__all__ = ["DefaultToolRegistry"]
