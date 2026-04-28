"""模块说明（中文）：`extensions/channels/feishu.py`。

飞书渠道实现：WebSocket 长连接（默认）+ Webhook（备选）两种接入模式。

环境变量：
- FEISHU_APP_ID / FEISHU_APP_SECRET：必填，用于 SDK 鉴权
- FEISHU_VERIFICATION_TOKEN：webhook 模式必填，用于签名验证
- FEISHU_CONNECTION_MODE：可选，"websocket"（默认）或 "webhook"
- FEISHU_ENDPOINT：可选，飞书 API 端点（默认 open.feishu.cn）

WebSocket 模式（默认）：
- 无需公网 URL——通过飞书官方 SDK (lark-oapi) 建立出站长连接
- SDK 内部自动处理：token 获取 → WebSocket 地址获取 → 建连 → 断线重连
- 事件回调接到 IncomingMessage → agent_cb 管线

解耦要点：
- 飞书渠道是完全自包含的——不 import core 任何模块
- try_create_feishu_channel() 在环境变量缺失时返回 None（而非抛异常）
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from typing import Any, Callable, Awaitable

import structlog

from extensions.channels.base import Channel, ChannelConfig, IncomingMessage
from extensions.channels.feishu_card_utils import build_thinking_card, build_answer_card

logger = structlog.get_logger("openagentic.channels.feishu")

# agent 回调签名
AgentCallback = Callable[[IncomingMessage], Awaitable[str]]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class FeishuChannel(Channel):
    """飞书消息渠道。

    两种连接模式：
    - websocket（默认）：服务端主动连接飞书事件网关，无需公网 URL
    - webhook：飞书主动 POST 消息到服务端，需要公网 URL

    WebSocket 模式通过 start()/stop() 管理生命周期。
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.verification_token: str = config.extra.get("verification_token", "")
        self.endpoint: str = config.extra.get("endpoint", "open.feishu.cn")
        self.connection_mode: str = config.extra.get("connection_mode", "websocket")

        # WebSocket 模式内部状态
        self._ws_task: asyncio.Task | None = None
        self._ws_stop: asyncio.Event = asyncio.Event()
        self._agent_cb: AgentCallback | None = None
        self._tenant_token: str | None = None
        self._token_expires_at: float = 0.0

    # -- Channel 接口实现 ---------------------------------------------------

    def cli_binary(self) -> str:
        return "lark-cli"

    # -- 生命周期（WebSocket 模式）------------------------------------------

    async def start(self, agent_cb: AgentCallback | None = None) -> None:
        """启动 WebSocket 长连接（仅 websocket 模式）。

        agent_cb：收到消息时调用的回调，签名为 async (IncomingMessage) -> str。
        """
        if self.connection_mode != "websocket":
            logger.info("Feishu channel in webhook mode, skipping WebSocket start")
            return

        self._agent_cb = agent_cb
        self._ws_stop.clear()
        self._ws_task = asyncio.create_task(self._ws_connect_loop())
        logger.info("Feishu WebSocket mode started")

    async def stop(self) -> None:
        """关闭 WebSocket 长连接。"""
        if self._ws_task and not self._ws_task.done():
            self._ws_stop.set()
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            logger.info("Feishu WebSocket stopped")
        self._ws_task = None

    # -- Webhook 模式 -------------------------------------------------------

    async def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        """验证飞书 webhook 签名（仅 webhook 模式使用）。"""
        try:
            payload = json.loads(body)
            if payload.get("type") == "url_verification":
                return True
        except Exception:
            pass

        ts = headers.get("x-lark-request-timestamp", "")
        nonce = headers.get("x-lark-request-nonce", "")
        signature = headers.get("x-lark-signature", "")

        if not ts or not nonce or not signature:
            logger.warning("Feishu webhook missing required headers")
            return False

        if not self.verification_token:
            logger.warning("FEISHU_VERIFICATION_TOKEN not set")
            return False

        try:
            if abs(int(time.time()) - int(ts)) > 300:
                logger.warning("Feishu webhook timestamp out of range: %s", ts)
                return False
        except ValueError:
            return False

        expected = hashlib.sha256(
            f"{ts}{nonce}{self.verification_token}".encode()
        ).hexdigest()
        return signature == expected

    async def parse_message(self, body: dict[str, Any]) -> IncomingMessage:
        """从飞书事件 body 解析消息。

        处理三种输入：
        1. WebSocket 事件（header.event_type 在外层）
        2. Webhook URL 验证（type=url_verification）
        3. Webhook 消息事件（im.message.receive_v1）
        """
        # URL 验证请求（webhook 模式）
        if body.get("type") == "url_verification":
            return IncomingMessage(
                platform="feishu", chat_id="", sender_id="system",
                sender_name="飞书平台", text="__url_verification__", raw=body,
            )

        # 提取事件体：兼容 WebSocket 的 header/event 结构和 webhook 的平铺结构
        header = body.get("header", {})
        event_type = header.get("event_type", body.get("type", ""))
        event = body.get("event", body)

        # 仅处理消息事件
        if "message" not in str(event_type):
            logger.debug("Feishu non-message event: %s", event_type)
            return IncomingMessage(
                platform="feishu", chat_id="", sender_id="system",
                sender_name="飞书系统", text=f"__{event_type}__", raw=body,
            )

        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_id_map = sender.get("sender_id", {})

        chat_id = message.get("chat_id", "")
        content = message.get("content", "{}")

        text, msg_type = _parse_content(content)
        sender_user_id = sender_id_map.get("user_id", sender_id_map.get("open_id", ""))
        sender_open_id = sender_id_map.get("open_id", "")

        return IncomingMessage(
            platform="feishu",
            chat_id=chat_id,
            sender_id=sender_user_id,
            sender_open_id=sender_open_id,
            sender_name=sender.get("sender_name", ""),
            text=_strip_mentions(text).strip() if msg_type == "text" else text,
            msg_type=msg_type,
            raw=body,
        )

    async def send_thinking_card(self, chat_id: str) -> str | None:
        """发送一张"思考中"交互卡片，返回 message_id 供后续更新。"""
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1.model.create_message_request import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )
        except ImportError:
            return None
        try:
            client = lark.Client.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            card = build_thinking_card()
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .content(json.dumps(card, ensure_ascii=False))
                    .msg_type("interactive")
                    .build()) \
                .build()
            resp = await client.im.v1.message.acreate(req)
            if resp.code == 0:
                msg_id = getattr(resp.data, "message_id", "")
                logger.info("Thinking card sent: %s", msg_id)
                return msg_id or None
            logger.error("Card send failed: code=%s msg=%s", resp.code, resp.msg)
            return None
        except Exception:
            logger.exception("Card send exception")
            return None

    async def update_card(self, message_id: str, markdown: str) -> bool:
        """更新交互卡片的内容（替换"思考中"为真实答案）。"""
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1.model.patch_message_request import (
                PatchMessageRequest,
                PatchMessageRequestBody,
            )
        except ImportError:
            return False
        try:
            client = lark.Client.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            card = build_answer_card(markdown)
            req = PatchMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(PatchMessageRequestBody.builder()
                    .content(json.dumps(card, ensure_ascii=False))
                    .build()) \
                .build()
            resp = await client.im.v1.message.apatch(req)
            if resp.code == 0:
                return True
            logger.error("Card update failed: code=%s msg=%s", resp.code, resp.msg)
            return False
        except Exception:
            logger.exception("Card update exception")
            return False

    async def send_message(self, chat_id: str, text: str) -> bool:
        """发送文本消息到指定会话——优先走 SDK 直发，备选 lark-cli。

        发送前自动将 Markdown/ASCII 表格替换为纯文本列表格式。
        """
        if not chat_id:
            logger.error("Feishu send_message: empty chat_id")
            return False
        # CLI 优先——支持 Markdown 渲染（内部转飞书 post 格式）
        # SDK 备选——纯文本兜底
        if await self._send_via_cli(chat_id, text):
            return True
        return await self._send_via_sdk(chat_id, text)

    async def _send_via_sdk(self, chat_id: str, text: str) -> bool:
        """通过 lark-oapi SDK 直发消息（无子进程开销）。"""
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1.model.create_message_request import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )
        except ImportError:
            return False
        try:
            client = lark.Client.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            content = json.dumps({"text": text}, ensure_ascii=False)
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .content(content)
                    .msg_type("text")
                    .build()) \
                .build()
            resp = await client.im.v1.message.acreate(req)
            if resp.code == 0:
                return True
            logger.error("SDK send failed: code=%s msg=%s", resp.code, resp.msg)
            return False
        except Exception:
            logger.exception("SDK send exception, falling back to CLI")
            return False

    async def _send_via_cli(self, chat_id: str, text: str) -> bool:
        """通过 lark-cli 发送消息（备选方案）。"""
        if not await self._check_cli():
            return False
        returncode, stdout, stderr = await self._run_cli(
            "im", "+messages-send",
            "--as", "bot",
            "--chat-id", chat_id,
            "--markdown", text,
        )
        if returncode != 0:
            logger.error("lark-cli send failed (rc=%d): %s", returncode, stderr or stdout)
            return False
        return True

    # -- WebSocket 连接管理（通过飞书官方 SDK lark-oapi）------------------

    async def _ws_connect_loop(self) -> None:
        """使用飞书官方 SDK 建立 WebSocket 长连接。

        直接调用 lark-oapi SDK 内部的异步 _connect() 方法，
        绕过 SDK 的同步 start()——避开 run_until_complete 与现有事件循环的冲突。
        SDK 内部自动处理：token 获取 → WS 地址获取 → 建连 → 事件分发 → 断线重连。
        """
        try:
            import lark_oapi as lark
        except ImportError:
            logger.error("lark-oapi not installed. Run: pip install lark-oapi")
            return

        # 构建事件处理器——回调在 SDK 内部的 asyncio 循环中执行
        def _on_message_v2(data) -> None:
            """SDK v2.0 事件回调（同步函数，在 SDK 自己的 asyncio 循环中执行）。"""
            try:
                event = getattr(data, "event", data)
                message = getattr(event, "message", {})
                sender = getattr(event, "sender", {})
                sid = getattr(sender, "sender_id", {})

                chat_id = getattr(message, "chat_id", "")
                content_str = getattr(message, "content", "{}")
                text, msg_type = _parse_content(content_str)
                if msg_type == "text":
                    text = _strip_mentions(text).strip()

                incoming = IncomingMessage(
                    platform="feishu",
                    chat_id=chat_id,
                    sender_id=getattr(sid, "user_id", "") or getattr(sid, "open_id", ""),
                    sender_open_id=getattr(sid, "open_id", "") or "",
                    sender_name=getattr(sender, "sender_name", ""),
                    text=text,
                    msg_type=msg_type,
                    raw={"sdk_v2": True},
                )
                if incoming.text:
                    logger.info("Feishu msg: sender=%s chat=%s type=%s text=%.100s",
                                incoming.sender_id, incoming.chat_id, incoming.msg_type, incoming.text)
                    # 在 SDK 自己的 loop 中调度 agent 回调
                    asyncio.ensure_future(self._reply_via_agent(incoming))
            except Exception:
                logger.exception("Feishu SDK v2 handler error")

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(_on_message_v2)
            .build()
        )

        client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("Feishu SDK WebSocket starting (app_id=%s...)", self.config.app_id[:10])

        # 直接调用 SDK 内部的 async _connect()，不经过同步 start()
        try:
            await client._connect()
        except asyncio.CancelledError:
            logger.info("Feishu SDK WebSocket cancelled")
            await client._disconnect()
        except Exception:
            logger.exception("Feishu SDK WebSocket error")

    async def _reply_via_agent(self, incoming: IncomingMessage) -> None:
        """统一的 agent 回调 + 回复发送。

        非文本消息（图片/视频/文件/表情包）不调 LLM，直接返回能力边界说明。
        """
        if not self._agent_cb:
            return

        # 非文本消息：直接回复，不走 LLM
        if incoming.msg_type in _NON_TEXT_REPLIES:
            reply = _NON_TEXT_REPLIES[incoming.msg_type]
            if incoming.chat_id:
                await self.send_message(incoming.chat_id, reply)
            return

        try:
            reply = await asyncio.wait_for(
                self._agent_cb(incoming), timeout=180.0
            )
        except asyncio.TimeoutError:
            logger.error("Agent callback timeout for feishu message")
            reply = "处理超时，请稍后重试。"
        except Exception:
            logger.exception("Agent callback failed")
            reply = "处理消息时出错，请稍后重试。"

        if reply.strip() and incoming.chat_id:
            await self.send_message(incoming.chat_id, reply)


def try_create_feishu_channel() -> FeishuChannel | None:
    """按环境变量尝试创建飞书渠道。

    返回 None 表示环境变量未配置（非异常），调用方应静默跳过。
    """
    app_id = _env("FEISHU_APP_ID")
    app_secret = _env("FEISHU_APP_SECRET")
    verification_token = _env("FEISHU_VERIFICATION_TOKEN")
    endpoint = _env("FEISHU_ENDPOINT", "open.feishu.cn")
    connection_mode = _env("FEISHU_CONNECTION_MODE", "websocket").lower()

    config = ChannelConfig(
        platform="feishu",
        app_id=app_id,
        app_secret=app_secret,
        extra={
            "verification_token": verification_token,
            "endpoint": endpoint,
            "connection_mode": connection_mode,
        },
    )

    if not config.is_configured():
        logger.debug("Feishu channel not configured (FEISHU_APP_ID/FEISHU_APP_SECRET missing)")
        return None

    if connection_mode == "webhook" and not verification_token:
        logger.warning(
            "FEISHU_VERIFICATION_TOKEN not set — webhook signature verification will fail. "
            "Get it from: 飞书开放平台 → 应用 → 事件订阅 → Verification Token"
        )

    logger.info("Feishu channel mode: %s", connection_mode)
    return FeishuChannel(config)


def _parse_content(content: Any) -> tuple[str, str]:
    """从飞书消息 content 中提取 (text, msg_type)。

    飞书不同类型的消息 content JSON 结构：
    - text:    {"text": "..."}
    - image:   {"image_key": "..."}
    - media:   {"file_key": "...", "image_key": "...", "file_name": "..."}
    - file:    {"file_key": "..."}
    - post:    {"title": "...", "content": [[...]]}
    - sticker: {"file_key": "..."}
    """
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            return content, "text"

    if not isinstance(content, dict):
        return str(content), "text"

    # 按优先级判定消息类型
    if "text" in content:
        return content["text"], "text"
    elif "image_key" in content and "file_key" in content:
        # media 类型同时有 image_key + file_key
        file_name = content.get("file_name", "")
        return f"[视频消息: {file_name}]" if file_name else "[视频消息]", "media"
    elif "image_key" in content:
        return "[图片消息]", "image"
    elif "file_key" in content:
        file_name = content.get("file_name", "")
        return f"[文件消息: {file_name}]" if file_name else "[文件消息]", "file"
    elif "content" in content:
        # post 富文本，提取 title + 文本
        title = content.get("title", "")
        post_blocks = content.get("content", [])
        post_text = _extract_post_text(post_blocks)
        full = f"{title}\n{post_text}".strip()
        return full, "post"
    elif "sticker_key" in content:
        return "[表情包]", "sticker"
    else:
        return "", "unknown"


def _extract_post_text(blocks: list) -> str:
    """从飞书 post 富文本的 content 二维数组中提取纯文本。"""
    lines = []
    for paragraph in blocks:
        if not isinstance(paragraph, list):
            continue
        line_parts = []
        for el in paragraph:
            if isinstance(el, dict):
                line_parts.append(el.get("text", ""))
        if line_parts:
            lines.append("".join(line_parts))
    return "\n".join(lines)


# 非文本消息的预设回复（不调 LLM，避免浪费 token）
_NON_TEXT_REPLIES = {
    "image": (
        "收到图片啦~ 不过目前我只支持识别**文字消息**，还无法理解图片内容。\n\n"
        "请用文字描述你想做什么，我会尽力帮你处理。"
    ),
    "media": (
        "收到视频啦~ 不过目前我只支持识别**文字消息**，还无法理解视频内容。\n\n"
        "请用文字描述你想做什么，我会尽力帮你处理。"
    ),
    "file": (
        "收到文件啦~ 不过目前我只支持识别**文字消息**，还无法解析文件内容。\n\n"
        "请用文字描述你想做什么，我会尽力帮你处理。"
    ),
    "sticker": (
        "表情包收到了，但我不太懂这个 😄\n请用文字告诉我你想做什么~"
    ),
}


def _strip_mentions(text: str) -> str:
    """移除 @用户 提及，保留纯文本内容。"""
    import re
    text = re.sub(r"@_user_\w+", "", text)
    text = re.sub(r"@_all", "", text)
    text = re.sub(r"@\S+", "", text)
    return text
