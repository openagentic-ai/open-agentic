"""AdapterRegistry——按环境变量发现并管理 adapter 生命周期。

替代 channels/__init__.py 的 register_channel_routes / start_channels / stop_channels。

参考: docs/ADR-001-multi-adapter-foundation.md §1, §3, §8
"""
from __future__ import annotations
import structlog
from typing import Iterable

from extensions.adapters.base import Adapter

logger = structlog.get_logger("openagentic.adapters.registry")


class AdapterRegistry:
    """全局 adapter 注册表。Phase 1 实现。"""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """注册 adapter(覆盖旧实例)。"""
        ...

    def get(self, adapter_id: str) -> Adapter | None: ...

    def all(self) -> Iterable[Adapter]: ...

    async def start_all(self, orchestrator) -> None:
        """启动全部 adapter;单个失败不影响其他(隔离)。"""
        ...

    async def stop_all(self) -> None: ...


def discover_from_env() -> AdapterRegistry:
    """按环境变量发现已配置的 adapter。Phase 1 实现:

    - FEISHU_APP_ID 存在 → 加载 extensions.adapters.feishu
    - WECOM_CORP_ID 存在 → 加载 extensions.adapters.wecom
    - DINGTALK_APP_KEY 存在(P1)→ 加载 extensions.adapters.dingtalk
    """
    return AdapterRegistry()
