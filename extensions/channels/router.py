"""模块说明（中文）：`extensions/channels/router.py`。

动态路由工厂：为每个已激活的渠道注册 webhook 端点。

支持的 webhook 模式：
- POST + JSON：飞书消息事件 + URL 验证（challenge）
- GET：企业微信 URL 验证（echostr 解密）
- POST + XML：企业微信消息事件（Encrypt 解密）

每个 webhook 端点处理流程：
1. 特殊请求穿透（URL 验证 → 直接返回 challenge/echostr 响应）
2. 验签（Channel.verify_webhook）
3. 解析消息（Channel.parse_message）
4. 调用 agent 回调获取回复
5. 通过 Channel.send_message 发送回复

解耦要点：
- 此模块不知道具体渠道实现——只依赖 Channel 抽象接口
- agent 回调由外部注入，不 import agent 模块
- 每个渠道的 webhook 路径不同，但共享相同的处理逻辑模板
"""

from __future__ import annotations

import structlog
from typing import Any, Callable, Awaitable

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from extensions.channels.base import Channel, IncomingMessage

logger = structlog.get_logger("openagentic.channels.router")

# agent 回调签名：async (IncomingMessage) -> str
# 由 main.py 注入，在其内部管理 DB session
AgentCallback = Callable[[IncomingMessage], Awaitable[str]]


def _make_webhook_handler(channel: Channel, agent_cb: AgentCallback | None):
    """为指定渠道创建一个 webhook 处理函数（闭包）。

    每个渠道有独立的处理函数，但逻辑完全相同——只是闭包捕获的 channel 实例不同。
    支持 GET（企微 URL 验证）和 POST（消息事件）两种 HTTP 方法。
    """

    async def webhook(request: Request):
        platform = channel.config.platform

        # ================================================================
        # GET 请求：企业微信 URL 验证
        # ================================================================
        if request.method == "GET":
            return await _handle_get_verification(channel, request)

        # ================================================================
        # POST 请求：消息事件 / 飞书 URL 验证
        # ================================================================
        body = await request.body()
        headers = dict(request.headers)

        # -- 飞书 URL 验证（type=url_verification）-----------------------
        try:
            payload: dict[str, Any] = __import__("json").loads(body)
            if payload.get("type") == "url_verification":
                challenge = payload.get("challenge", "")
                logger.info("Feishu URL verification received, responding with challenge")
                return JSONResponse({"challenge": challenge})
        except Exception:
            payload = {}  # 非 JSON body（如 XML），后续处理

        # -- 企微 XML 消息：包装为 JSON 传给 parse_message ----------------
        content_type = request.headers.get("content-type", "")
        if "xml" in content_type or (body and body.startswith(b"<xml>")):
            raw_xml = body.decode("utf-8", errors="replace")
            # 企微 POST 消息：query params 中包含 msg_signature/timestamp/nonce
            payload = {
                "raw_xml": raw_xml,
                "msg_signature": request.query_params.get("msg_signature", ""),
                "timestamp": request.query_params.get("timestamp", ""),
                "nonce": request.query_params.get("nonce", ""),
            }
            # 验签（企微 XML 消息使用 query params 中的签名参数）
            if not await _verify_wecom_xml_signature(channel, raw_xml, request.query_params):
                logger.warning("WeCom XML signature verification failed")
                raise HTTPException(status_code=403, detail="Signature verification failed")

        # -- 标准 JSON 消息体验签 -----------------------------------------
        if "xml" not in content_type and not (body and body.startswith(b"<xml>")):
            if not await channel.verify_webhook(body, headers):
                logger.warning("Webhook signature verification failed", platform=platform)
                raise HTTPException(status_code=403, detail="Signature verification failed")

        # -- 解析消息 -----------------------------------------------------
        incoming = await channel.parse_message(payload)

        # 跳过 URL 验证占位消息
        if incoming.text == "__url_verification__":
            logger.info("URL verification placeholder, skipping agent", platform=platform)
            return {"status": "ok", "note": "url_verification_handled"}

        logger.info(
            "Channel message",
            platform=incoming.platform,
            sender=incoming.sender_id,
            chat=incoming.chat_id,
            text=incoming.text[:200],
        )

        # -- 路由到 agent ------------------------------------------------
        reply_text = ""
        if agent_cb:
            try:
                reply_text = await agent_cb(incoming)
            except Exception:
                logger.exception("Agent callback failed", platform=platform)
                reply_text = "处理消息时出错，请稍后重试。"
        else:
            reply_text = "（agent 未就绪）"

        # -- 发送回复 -----------------------------------------------------
        if reply_text.strip() and incoming.chat_id:
            sent = await channel.send_message(incoming.chat_id, reply_text)
            if not sent:
                logger.error("Failed to send reply", platform=platform, chat_id=incoming.chat_id)
        else:
            logger.info("Empty reply or no chat_id, skipping send", platform=platform)

        return {"status": "ok"}

    webhook.__name__ = f"webhook_{channel.config.platform}"
    return webhook


async def _handle_get_verification(channel: Channel, request: Request) -> Response:
    """处理企业微信 GET URL 验证请求。

    企微验证流程：
    1. GET 请求带 echostr、msg_signature、timestamp、nonce 参数
    2. 验签 + 解密 echostr
    3. 返回解密后的明文（PlainTextResponse）
    """
    echostr = request.query_params.get("echostr", "")
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")

    if not echostr:
        logger.warning("WeCom GET verification missing echostr")
        return PlainTextResponse("missing echostr", status_code=400)

    logger.info("WeCom URL verification", echostr=echostr[:20])

    # 使用渠道特有的 echostr 解密方法
    try:
        plain = getattr(channel, "get_echostr_response")(echostr)
        return PlainTextResponse(plain)
    except Exception:
        logger.exception("WeCom echostr decryption failed")
        return PlainTextResponse("decryption failed", status_code=500)


async def _verify_wecom_xml_signature(
    channel: Channel, raw_xml: str, query_params: Any
) -> bool:
    """验签企微 XML POST 消息。

    企微签名：SHA1(sort([token, timestamp, nonce, msg_encrypt]))
    其中 msg_encrypt 是 XML 中 <Encrypt> 的文本内容。
    """
    token = getattr(channel, "token", "")
    if not token:
        return False

    msg_signature = query_params.get("msg_signature", "")
    timestamp = query_params.get("timestamp", "")
    nonce = query_params.get("nonce", "")

    if not msg_signature or not timestamp or not nonce:
        return False

    # 提取 Encrypt 文本
    import re
    match = re.search(r"<Encrypt>(.*?)</Encrypt>", raw_xml)
    if not match:
        return False
    msg_encrypt = match.group(1)

    # SHA1(sort([token, timestamp, nonce, msg_encrypt]))
    parts = sorted([token, timestamp, nonce, msg_encrypt])
    expected = __import__("hashlib").sha1("".join(parts).encode()).hexdigest()

    return msg_signature == expected


def build_channel_router(
    channels: dict[str, Channel],
    agent_cb: AgentCallback | None,
) -> APIRouter:
    """为所有已激活渠道构建统一的 APIRouter。

    生成路由：
    - GET/POST /api/channels/feishu/webhook
    - GET/POST /api/channels/wecom/webhook

    channels: {platform_name: Channel 实例}
    agent_cb: agent 路由回调（可为 None，此时渠道仅返回确认消息）
    """
    router = APIRouter(prefix="/api/channels", tags=["channels"])

    for platform, channel in channels.items():
        handler = _make_webhook_handler(channel, agent_cb)
        router.add_api_route(
            path=f"/{platform}/webhook",
            endpoint=handler,
            methods=["GET", "POST"],
            summary=f"{platform} webhook",
            description=f"接收 {platform} 消息事件与 URL 验证的 webhook 端点",
        )

    # 渠道列表查询接口
    @router.get("")
    async def list_channels():
        """列出当前激活的渠道及其状态。"""
        return {
            platform: {
                "app_id": ch.config.app_id[:8] + "***" if ch.config.app_id else "",
                "cli_available": ch._cli_checked,
            }
            for platform, ch in channels.items()
        }

    return router
