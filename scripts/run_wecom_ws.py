"""企业微信 WebSocket 监听脚本——支持工具调用（run_command / read_file）。

复用 ``extensions.channels.channel_runner.ChannelAIService`` 作为 AI 底座。
对接企业微信 webhook 模式（需公网 URL 或内网穿透）。

环境变量：
- WECOM_CORP_ID / WECOM_APP_SECRET：必填
- WECOM_TOKEN / WECOM_ENCODING_AES_KEY：必填（webhook 验签/解密）
- OPENAGENTIC_MODEL / OPENAI_API_KEY：LLM 配置
"""
import asyncio, logging, signal, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 关掉 litellm 远程 cost map 拉取
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from extensions.channels.channel_runner import ChannelAIService
from extensions.channels.wecom import try_create_wecom_channel

stop = asyncio.Event()


async def main():
    ch = try_create_wecom_channel()
    if not ch:
        logging.error("FAIL: Channel not created — check .env (WECOM_CORP_ID/WECOM_APP_SECRET)")
        return

    ai = ChannelAIService(
        channel_hints=[
            "当前通过企业微信渠道接入。回复使用纯文本格式，不支持 Markdown 表格。",
        ],
    )

    # 企微 webhook 模式：通过 FastAPI 路由接收消息
    # 本脚本可配合 uvicorn 启动 webhook 端点：
    #   uvicorn scripts.run_wecom_ws:create_app --host 0.0.0.0 --port 8000
    # 或直接导入 extensions.channels.router 注册的 /api/channels/wecom/webhook
    logging.info(
        "企业微信渠道需通过 webhook 模式运行。\n"
        "方式一：uvicorn scripts.run_wecom_ws:create_app --host 0.0.0.0 --port 8000\n"
        "方式二：启动主 FastAPI 应用（已注册 wecom webhook 路由）"
    )

    # 方式一：内嵌 FastAPI 最小应用
    try:
        from fastapi import FastAPI, Request, HTTPException
    except ImportError:
        logging.error("FastAPI not installed. Run: pip install fastapi")
        return

    app = FastAPI(title="OpenAgentic-WeCom")

    @app.get("/api/channels/wecom/webhook")
    async def wecom_verify(msg_signature: str = "", timestamp: str = "", nonce: str = "",
                           echostr: str = ""):
        """企微 URL 验证"""
        if not echostr:
            raise HTTPException(400, "missing echostr")
        try:
            plain = ch.get_echostr_response(echostr)
            return plain
        except Exception as e:
            logging.exception("echostr decrypt failed")
            raise HTTPException(400, str(e))

    @app.post("/api/channels/wecom/webhook")
    async def wecom_event(request: Request, msg_signature: str = "", timestamp: str = "",
                          nonce: str = ""):
        """企微消息事件"""
        raw_body = await request.body()
        try:
            # 解析 XML 加密消息
            raw_xml = raw_body.decode("utf-8", errors="replace")
            msg = ch._parse_xml_message(raw_xml)
            if msg.text and msg.text not in ("[parse_error:", "__url_verification__"):
                logging.info(">>> %s: %s", msg.sender_id, msg.text)
                reply = await ai.reply(msg.text, msg.chat_id or "default")
                if msg.chat_id and reply:
                    await ch.send_message(msg.chat_id, reply)
            return "success"
        except Exception as e:
            logging.exception("WeCom event failed")
            return "fail"

    @app.on_event("startup")
    async def startup():
        logging.info("企业微信 Webhook 服务已启动，等待消息...")

    sig_handler = lambda: stop.set()

    return app


def create_app():
    """供 uvicorn 调用的工厂函数。"""
    return asyncio.run(main())


if __name__ == "__main__":
    # 直接运行时嵌入 uvicorn
    import uvicorn
    app = asyncio.get_event_loop().run_until_complete(main())
    # Note: asyncio.run(main()) returns the app after setup
    # We need a different approach for __main__ usage
    logging.warning("Use: uvicorn scripts.run_wecom_ws:create_app --host 0.0.0.0 --port 8000")
