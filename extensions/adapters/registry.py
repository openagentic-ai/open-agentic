"""AdapterRegistry——按环境变量发现并管理 adapter 生命周期。

替代 channels/__init__.py 的 register_channel_routes / start_channels / stop_channels。

设计:
- 每个 adapter 包(如 extensions.adapters.feishu)暴露 `create_adapter()` 工厂
- registry 只持有 (adapter_id → Adapter 实例) 映射;不知道飞书/企微细节
- discover_from_env 用 env var → 模块路径表声明"环境里有什么就加载什么"
- 启动单个 adapter 失败 → 仅 warning,不影响其他(隔离原则)

参考: docs/ADR-001-multi-adapter-foundation.md §1, §3, §8
"""
from __future__ import annotations

import importlib
import os
import structlog
from typing import Iterable

from extensions.adapters.base import Adapter

logger = structlog.get_logger("openagentic.adapters.registry")


# (env_var → 模块路径) 声明:env 设置即视为该端启用,加载对应包的 create_adapter()。
# adapter 自己读后续配置 env(如 FEISHU_APP_SECRET)。
_ADAPTER_DISCOVERY: dict[str, str] = {
    "FEISHU_APP_ID": "extensions.adapters.feishu",
    "WECOM_CORP_ID": "extensions.adapters.wecom",
    "DINGTALK_APP_KEY": "extensions.adapters.dingtalk",
}


class AdapterRegistry:
    """全局 adapter 注册表。"""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """注册 adapter(同 adapter_id 会覆盖旧实例)。"""
        if adapter.adapter_id in self._adapters:
            logger.warning("adapter overrides existing", adapter_id=adapter.adapter_id)
        self._adapters[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> Adapter | None:
        return self._adapters.get(adapter_id)

    def all(self) -> Iterable[Adapter]:
        return list(self._adapters.values())

    async def start_all(self, orchestrator) -> None:
        """启动全部 adapter;单个失败不影响其他(隔离)。"""
        for adapter in list(self._adapters.values()):
            try:
                await adapter.start(orchestrator)
                logger.info("adapter started", adapter_id=adapter.adapter_id)
            except Exception as exc:
                logger.warning(
                    "adapter start failed (isolated)",
                    adapter_id=adapter.adapter_id,
                    error=str(exc),
                )

    async def stop_all(self) -> None:
        for adapter in list(self._adapters.values()):
            try:
                await adapter.stop()
                logger.info("adapter stopped", adapter_id=adapter.adapter_id)
            except Exception as exc:
                logger.warning(
                    "adapter stop failed (isolated)",
                    adapter_id=adapter.adapter_id,
                    error=str(exc),
                )


def discover_from_env(*, env: dict[str, str] | None = None) -> AdapterRegistry:
    """按环境变量发现已配置的 adapter,加载对应包的 create_adapter() 工厂。

    - env=None 时读取 os.environ
    - 模块没有 create_adapter 或加载抛异常 → warning + 跳过(隔离)
    """
    src = env if env is not None else os.environ
    registry = AdapterRegistry()
    for env_var, module_path in _ADAPTER_DISCOVERY.items():
        if not src.get(env_var):
            continue
        try:
            mod = importlib.import_module(module_path)
        except Exception as exc:
            logger.warning(
                "adapter import failed (skipped)",
                module=module_path, env=env_var, error=str(exc),
            )
            continue
        factory = getattr(mod, "create_adapter", None)
        if factory is None:
            logger.warning(
                "adapter missing create_adapter() factory (skipped)",
                module=module_path, env=env_var,
            )
            continue
        try:
            adapter = factory()
        except Exception as exc:
            logger.warning(
                "adapter factory failed (skipped)",
                module=module_path, env=env_var, error=str(exc),
            )
            continue
        registry.register(adapter)
        logger.info(
            "adapter discovered",
            module=module_path, env=env_var, adapter_id=adapter.adapter_id,
        )
    return registry


__all__ = ["AdapterRegistry", "discover_from_env"]
