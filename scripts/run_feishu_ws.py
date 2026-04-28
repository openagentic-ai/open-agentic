"""飞书 WebSocket 监听脚本——支持工具调用（run_command / read_file / lark-cli）。

复用 ``extensions.channels.channel_runner.ChannelAIService`` 作为 AI 底座。
"""
import asyncio, signal, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 关掉 litellm 远程 cost map 拉取——走代理每次超时 6 秒
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
# 确保 API 调用直连不过代理（飞书国内服务无需代理）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
          "ALL_PROXY", "all_proxy", "SOCKS_PROXY", "socks_proxy"):
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

# 日志统一走 structlog → 控制台 + log/feishu_bot.log
from openagentic.observability.logging import configure_logging
configure_logging(level="INFO", log_file="feishu_bot.log")

import structlog
logger = structlog.get_logger("openagentic.channels.feishu")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from extensions.channels.channel_runner import ChannelAIService, LARK_TOOL
from extensions.channels.feishu import try_create_feishu_channel

stop = asyncio.Event()


async def main():
    ch = try_create_feishu_channel()
    if not ch:
        logger.error("FAIL: Channel not created — check .env")
        return

    ai = ChannelAIService(
        extra_tools=[LARK_TOOL],
        channel_hints=[
            "当前通过飞书卡片回复（lark_md 格式），回复前检查：有表格→先调 lark_cli base 创建多维表格再贴链接；有代码→先调 lark_cli doc 创建文档再贴链接。",
            "飞书工具优先：能用 lark_cli 处理的事（日程/文档/表格/审批/邮件/云盘/任务/会议/OKR/考勤/通讯录等）直接调用，不要用 run_command 绕路。",
            "回复简洁，先动手再说话。",
        ],
    )

    async def callback(msg):
        logger.info("feishu_msg", sender=msg.sender_id, text=msg.text[:100])
        card_id = await ch.send_thinking_card(msg.chat_id)
        try:
            reply = await ai.reply(
                msg.text, msg.chat_id,
                platform=msg.platform,
                sender_open_id=msg.sender_open_id,
            )
            logger.info("ai_reply", length=len(reply), preview=reply[:300])
            if card_id:
                await ch.update_card(card_id, reply)
            elif reply:
                await ch.send_message(msg.chat_id, reply)
        except asyncio.CancelledError:
            # 超时触发——_reply_via_agent 的 180s wait_for 超时取消本协程，
            # CancelledError 是 BaseException，不会被 except Exception 捕获
            err_msg = "处理超时，请稍后重试。"
            logger.warning("ai_reply timeout", sender=msg.sender_id)
            if card_id:
                try:
                    await ch.update_card(card_id, err_msg)
                except Exception:
                    pass
        except Exception as e:
            logger.exception("ai_reply failed", error=str(e)[:200])
            err_msg = f"抱歉，处理请求时出错：{e}"
            if card_id:
                await ch.update_card(card_id, err_msg)
            else:
                await ch.send_message(msg.chat_id, err_msg)
        return ""

    ch._ws_stop = stop
    await ch.start(agent_cb=callback)
    logger.info("ws_started", msg="WebSocket 已启动，等待飞书消息...")
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop.set())
    await stop.wait()
    await ch.stop()
    logger.info("ws_stopped")


asyncio.run(main())
