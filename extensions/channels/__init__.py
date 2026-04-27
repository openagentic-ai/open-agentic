"""模块说明（中文）：`extensions/channels/__init__.py`。

Channel 注册中心：按环境变量发现已配置的渠道，生成 FastAPI webhook 路由。

设计原则（解耦）：
- 渠道与核心完全隔离——core 不 import extensions
- 按环境变量自动发现：有 FEISHU_APP_ID 才激活飞书，有 WECOM_CORP_ID 才激活企微
- 渠道加载失败（CLI 未安装/config 缺失）仅日志警告，不影响其他渠道
- main.py 只需一行 `register_channel_routes(app)` 即可接入
"""

from __future__ import annotations

import structlog

from fastapi import FastAPI

from extensions.channels.base import Channel, ChannelConfig, IncomingMessage
from extensions.channels.router import build_channel_router

logger = structlog.get_logger("openagentic.channels")

# 全局渠道注册表：{platform: Channel}
_registry: dict[str, Channel] = {}

# agent 路由回调：webhook 收到消息后调此函数执行 agent 并返回回复
# 签名：async (IncomingMessage) -> str
_agent_callback = None


def set_agent_callback(cb) -> None:
    """注册 agent 路由回调函数。

    cb 签名为 async (IncomingMessage) -> str，返回 agent 回复文本。
    由 main.py 在 create_app() 中注入，实现 channel ↔ agent 解耦。
    """
    global _agent_callback
    _agent_callback = cb


def _discover_channels() -> dict[str, Channel]:
    """按环境变量发现已配置的渠道（延迟导入，隔离加载失败）。"""
    from extensions.channels.feishu import try_create_feishu_channel
    from extensions.channels.wecom import try_create_wecom_channel

    channels: dict[str, Channel] = {}

    feishu = try_create_feishu_channel()
    if feishu:
        channels["feishu"] = feishu
        logger.info("Channel activated: feishu")

    wecom = try_create_wecom_channel()
    if wecom:
        channels["wecom"] = wecom
        logger.info("Channel activated: wecom")

    return channels


def register_channel_routes(app: FastAPI) -> dict[str, Channel]:
    """在 FastAPI 上注册所有已配置渠道的 webhook 路由。

    返回已激活的渠道字典，供调用方知道哪些渠道已就绪。
    同一 app 实例上多次调用不会重复注册（幂等）；新 app 实例会重新注册。
    """
    global _registry

    # 如果渠道尚未发现，先扫描环境变量
    if not _registry:
        _registry = _discover_channels()

    # 幂等：检查是否已在此 app 实例上注册过（通过 app 对象的 id）
    _already_registered = getattr(app, "_channels_registered", False)
    if _already_registered:
        return _registry

    if not _registry:
        logger.info("No channel configured (set FEISHU_APP_ID or WECOM_CORP_ID to activate)")
        app._channels_registered = True
        return _registry

    router = build_channel_router(_registry, _agent_callback)
    app.include_router(router)
    app._channels_registered = True
    return _registry


def get_channel(platform: str) -> Channel | None:
    """按平台名获取已激活渠道。"""
    return _registry.get(platform)


async def start_channels() -> None:
    """启动所有已激活渠道的长连接（WebSocket 等）。

    在 FastAPI lifespan startup 中调用。
    每个渠道的 start() 失败仅日志警告，不影响其他渠道。
    """
    for platform, channel in _registry.items():
        try:
            await channel.start(agent_cb=_agent_callback)
        except Exception:
            logger.exception("Failed to start channel", platform=platform)


async def stop_channels() -> None:
    """关闭所有已激活渠道的长连接。

    在 FastAPI lifespan shutdown 中调用。
    每个渠道的 stop() 失败仅日志警告，不影响其他渠道。
    """
    for platform, channel in _registry.items():
        try:
            await channel.stop()
        except Exception:
            logger.exception("Failed to stop channel", platform=platform)


__all__ = [
    "Channel",
    "ChannelConfig",
    "IncomingMessage",
    "register_channel_routes",
    "set_agent_callback",
    "get_channel",
    "start_channels",
    "stop_channels",
]
