"""模块说明（中文）：`extensions/channels/base.py`。

Channel 抽象接口：定义消息渠道的统一契约。

所有渠道实现必须继承 Channel 并实现：
- verify_webhook()：验证请求签名/解密消息
- parse_message()：从 webhook 请求体提取 IncomingMessage
- send_message()：通过 CLI 发送回复消息

解耦要点：
- 渠道不依赖 core 模块（agent/auth/workflow），只定义数据类型
- 消息路由通过外部注入的回调完成，渠道本身不知道 agent 的存在
- CLI 调用统一走 _run_cli() 辅助函数，渠道实现不接触 subprocess
"""

from __future__ import annotations

import asyncio
import json
import structlog
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = structlog.get_logger("openagentic.channels.base")


@dataclass
class IncomingMessage:
    """从 webhook 解析出的标准化入站消息。

    渠道实现负责从各自的 webhook 格式转换为这个统一结构。
    """

    platform: str  # "feishu" | "wecom"
    chat_id: str  # 群聊 ID 或私聊 ID
    sender_id: str  # 发送者 open_id / user_id（来源由渠道决定，仅用于显示/日志）
    sender_open_id: str = ""  # 平台稳定主键——用于 user_channel_bindings 反查（飞书=open_id）
    sender_name: str = ""  # 发送者显示名（可选）
    text: str = ""  # 消息纯文本（@机器人 部分已剥离）
    msg_type: str = ""  # 消息类型："text" / "image" / "media" / "file" / "post" / "sticker" / "unknown"
    raw: dict[str, Any] = field(default_factory=dict)  # 原始 webhook payload（调试用）


@dataclass
class ChannelConfig:
    """渠道初始化配置。

    所有渠道共享的配置字段；渠道特有字段通过 extra 透传。
    """

    platform: str
    app_id: str  # 飞书 app_id / 企微 corp_id
    app_secret: str  # 飞书 app_secret / 企微 secret
    extra: dict[str, Any] = field(default_factory=dict)

    def is_configured(self) -> bool:
        """两个必填字段都非空才算已配置。"""
        return bool(self.app_id and self.app_secret)


class Channel(ABC):
    """消息渠道抽象基类。

    子类职责：
    - 封装特定平台的 webhook 验签与消息解析逻辑
    - 通过 CLI 发送消息（不直接调 API，统一走 CLI）

    生命周期（可选覆写）：
    - start()：渠道启动（如 WebSocket 长连接）
    - stop()：渠道关闭
    """

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config
        self._cli_checked: bool = False

    # -- 生命周期（子类可选覆写）----------------------------------------------

    async def start(self, agent_cb=None) -> None:
        """渠道启动回调——WebSocket 等长连接渠道在此建立持久连接。

        默认无操作；子类按需覆写。
        agent_cb 签名为 async (IncomingMessage) -> str。
        """

    async def stop(self) -> None:
        """渠道关闭回调——清理长连接、释放资源。

        默认无操作；子类按需覆写。
        """

    # -- 子类必须实现 ---------------------------------------------------------

    @abstractmethod
    async def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        """验证 webhook 请求的签名/Token，返回 True 表示合法。

        飞书：验 header 中的 timestamp + nonce + signature
        企微：验 URL 参数 msg_signature + 解密 echostr
        """
        ...

    @abstractmethod
    async def parse_message(self, body: dict[str, Any]) -> IncomingMessage:
        """从 webhook JSON body 解析出标准化入站消息。

        调用方保证 body 已经过 verify_webhook 验证。
        """
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, text: str) -> bool:
        """向指定会话发送文本消息，返回 True 表示成功。

        实现通过 CLI 子进程发送（lark-cli / wecom-cli）。
        """
        ...

    # -- CLI 辅助方法（供子类复用）-------------------------------------------

    async def _run_cli(self, *args: str, timeout: float = 30.0) -> tuple[int, str, str]:
        """异步执行 CLI 命令，返回 (returncode, stdout, stderr)。

        所有子类的 CLI 调用统一走这个方法，不直接操作 subprocess。
        """
        cmd = [self.cli_binary(), *args]
        logger.debug("CLI invoke", cmd=" ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return (-1, "", f"CLI timeout after {timeout}s")

        out_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = stderr.decode("utf-8", errors="replace").strip()
        return (proc.returncode or 0, out_text, err_text)

    @abstractmethod
    def cli_binary(self) -> str:
        """CLI 可执行文件名或完整路径。

        飞书返回 "lark-cli"，企微返回 "wecom-cli"。
        """
        ...

    async def _check_cli(self) -> bool:
        """检查 CLI 是否已安装，缓存结果避免重复探测。"""
        if self._cli_checked:
            return True
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary(), "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._cli_checked = proc.returncode == 0
        except FileNotFoundError:
            self._cli_checked = False
            logger.warning("CLI not found, channel degraded", cli=self.cli_binary(), platform=self.config.platform)
        return self._cli_checked

    def _try_parse_json(self, text: str) -> Any:
        """尝试将 CLI 输出解析为 JSON，失败则返回原始字符串。"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
