"""飞书 WebSocket 监听脚本——支持工具调用（run_command / read_file / lark-cli）。

复用 ``extensions.channels.channel_runner.ChannelAIService`` 作为 AI 底座。
"""
import asyncio, signal, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 关掉 litellm 远程 cost map 拉取——走代理每次超时 6 秒
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
# 确保 API 调用直连不过代理
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
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
            "当前通过飞书卡片回复，内容限制：lark_md 格式**不支持 Markdown 表格和围栏代码块**。",
            "回复规范：",
            "  - 纯文字回答用标题(#)/列表(-)/粗体(**)，它们是支持的",
            "  - 需要展示结构化数据/表格 → 调用 lark_cli base 创建多维表格，把表格链接贴到卡片里",
            "  - 需要展示代码/长文本 → 调用 lark_cli doc 创建飞书文档，把文档链接贴到卡片里",
            "  - 需要发送消息/文件/日程/审批等 → 调用对应的 lark_cli 子命令",
            "  - 不要输出 Markdown 表格（|...|）或围栏代码块（```），它们无法渲染",
            "回复简洁，优先用工具解决实际问题。",
        ],
    )

    async def callback(msg):
        logger.info("feishu_msg", sender=msg.sender_id, text=msg.text[:100])
        card_id = await ch.send_thinking_card(msg.chat_id)  # 先发"思考中"卡片
        reply = await ai.reply(                              # 再调 AI
            msg.text, msg.chat_id,
            platform=msg.platform,
            sender_open_id=msg.sender_open_id,
        )
        logger.info("ai_reply", length=len(reply), preview=reply[:300])
        if card_id:
            await ch.update_card(card_id, reply)
        elif reply:
            await ch.send_message(msg.chat_id, reply)
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
