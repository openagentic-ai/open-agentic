"""飞书 WebSocket 监听脚本——**双轨 demo 版**,走新底座 DefaultOrchestrator。

与 run_feishu_ws.py(走旧 ChannelAIService)并行存在,**不替换**生产服务。
本脚本仅用于本地手跑验证 P0-2 飞书迁底座可行性。

复用现有资产:
- channel_runner.execute_tool 当 DefaultOrchestrator 的 executor(零迁移)
- channel_runner 的 BASE_TOOLS / WORKFLOW_TOOLS / LARK_TOOL schema 注册到 ToolRegistry
- channel_runner._build_preset_hint / channel_runner.contextvars 不动
- feishu.try_create_feishu_channel / send_thinking_card / update_card 不动

跳过的:
- fast-path(走 LLM,慢但功能等价;真切时再迁 #4 IntentRouter)
- ConcurrencyGate(DefaultOrchestrator 自带 per-session 锁;后续可叠加全局 gate)
- working memory compression(暂不接;影响长会话 token 控制)

事件流 → 飞书卡片协议:
- ThinkingEvent: 仅 logger 输出,不刷新卡片(避免飞书限流)
- ToolCallEvent / ToolResultEvent: 仅 logger
- FinalEvent → update_card(终态)
- ErrorEvent → update_card(错误)
"""
import asyncio
import os
import signal
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 关掉 litellm 远程 cost map 拉取——走代理每次超时 6 秒
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
# 确保 API 调用直连不过代理(飞书国内服务无需代理)
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
          "ALL_PROXY", "all_proxy", "SOCKS_PROXY", "socks_proxy"):
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

from openagentic.observability.logging import configure_logging  # noqa: E402
configure_logging(level="INFO", log_file="feishu_bot_orchestrator.log")

import structlog  # noqa: E402
logger = structlog.get_logger("openagentic.channels.feishu.orchestrator")

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# 复用现有 channel_runner 资产
from extensions.channels import channel_runner  # noqa: E402
from extensions.channels.feishu import try_create_feishu_channel  # noqa: E402

from openagentic.application import (  # noqa: E402
    DefaultOrchestrator,
    DefaultSessionStore,
    DefaultToolRegistry,
    ErrorEvent,
    FinalEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolSpec,
)

ADAPTER_ID = "feishu"
stop = asyncio.Event()


async def _placeholder_handler(*args, **kwargs) -> str:
    """ToolSpec 字段必填,但 executor 已注入,handler 永不会被调。"""
    return ""


def _register_schema(reg: DefaultToolRegistry, schemas: list[dict]) -> None:
    """把 LiteLLM 风格 dict schema 列表转 ToolSpec 注册到 registry."""
    for entry in schemas:
        fn = entry.get("function") or {}
        name = fn.get("name") or ""
        if not name:
            continue
        reg.register_global(ToolSpec(
            name=name,
            description=fn.get("description", ""),
            parameters=fn.get("parameters") or {},
            handler=_placeholder_handler,
        ))


def _build_system_prompt(channel_hints: list[str]) -> str:
    """完整复用 ChannelAIService.__init__ 的 system prompt 拼装逻辑。"""
    from openagentic.identity import build_system_prompt
    sp = build_system_prompt(list(channel_hints) if channel_hints else None)

    # 注入可用系统预设工作流
    preset_hint = channel_runner._build_preset_hint()
    if preset_hint:
        sp += "\n" + preset_hint

    # Core memory
    try:
        from openagentic.cli.prompt import build_core_memory_section
        core = build_core_memory_section(limit=20)
        if core:
            sp += "\n" + core
    except Exception as exc:
        logger.warning("core_memory_inject_failed", error=str(exc))
    return sp


def _build_orchestrator() -> DefaultOrchestrator:
    """装配 DefaultOrchestrator——工具 schema 注册 + system prompt + executor 注入。"""
    reg = DefaultToolRegistry()
    _register_schema(reg, channel_runner.BASE_TOOLS)
    _register_schema(reg, channel_runner.WORKFLOW_TOOLS)
    _register_schema(reg, [channel_runner.LARK_TOOL])

    channel_hints = [
        "当前通过飞书卡片回复(lark_md 格式),回复前检查:有表格→先调 lark_cli base 创建多维表格再贴链接;有代码→先调 lark_cli doc 创建文档再贴链接。",
        "飞书工具优先:能用 lark_cli 处理的事(日程/文档/表格/审批/邮件/云盘/任务/会议/OKR/考勤/通讯录等)直接调用,不要用 run_command 绕路。",
        "回复简洁,先动手再说话。",
    ]
    system_prompt = _build_system_prompt(channel_hints)

    model = os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("OPENAGENTIC_MODEL") or ""
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_base = os.getenv("OPENAI_BASE_URL") if model.startswith("openai/") else None

    orch = DefaultOrchestrator(
        model=model,
        api_key=api_key,
        api_base=api_base,
        system_prompt=system_prompt,
        tool_registry=reg,
        executor=channel_runner.execute_tool,   # 直接复用统一工具分发器
        max_iterations=channel_runner.MAX_TOOL_ITERATIONS,
        enable_memory=True,                     # 复用 MemoryManager,与旧链路一致
    )
    logger.info(
        "orchestrator_ready",
        tool_count=len(reg.list_for(ADAPTER_ID)),
        model=model,
    )
    return orch


async def _consume_events_to_card(stream, ch, card_id: str | None, chat_id: str) -> str:
    """订阅事件流,渲染到飞书卡片。返回 final 文本(用于 logger)。"""
    final_text = ""
    async for ev in stream:
        if isinstance(ev, ThinkingEvent):
            logger.info("ev_thinking", seq=ev.seq, text=ev.text)
        elif isinstance(ev, ToolCallEvent):
            logger.info("ev_tool_call", seq=ev.seq, tool=ev.tool_name,
                        args_preview=str(ev.tool_args)[:120])
        elif isinstance(ev, ToolResultEvent):
            logger.info("ev_tool_result", seq=ev.seq, call_id=ev.call_id,
                        err=ev.error, result_preview=str(ev.result)[:120])
        elif isinstance(ev, FinalEvent):
            final_text = ev.text or "(空回复)"
            logger.info("ev_final", seq=ev.seq, length=len(final_text),
                        preview=final_text[:200])
            if card_id:
                await ch.update_card(card_id, final_text)
            else:
                await ch.send_message(chat_id, final_text)
        elif isinstance(ev, ErrorEvent):
            err_text = f"处理出错[{ev.code}]: {ev.message}"
            logger.warning("ev_error", seq=ev.seq, code=ev.code, msg=ev.message)
            if card_id:
                await ch.update_card(card_id, err_text)
            else:
                await ch.send_message(chat_id, err_text)
            final_text = err_text
    return final_text


async def main() -> None:
    ch = try_create_feishu_channel()
    if not ch:
        logger.error("feishu_channel_create_failed", msg="check .env")
        return

    orch = _build_orchestrator()
    store = DefaultSessionStore()

    async def callback(msg):
        logger.info("feishu_msg_in", sender=msg.sender_id,
                    chat_id=msg.chat_id, text=msg.text[:120])

        # 思考卡片占位
        card_id = await ch.send_thinking_card(msg.chat_id)

        # 设置 contextvars,让下游工具(workflow / lark_cli)继承
        # 同协程链路下游协程会自动继承 contextvars,无需手动传播
        token_platform = channel_runner._current_platform.set(msg.platform or "feishu")
        token_sender = channel_runner._current_sender_open_id.set(msg.sender_open_id or "")
        token_chat = channel_runner._current_chat_id.set(msg.chat_id or "")
        token_card = channel_runner._thinking_card_msg_id.set(card_id or "")

        try:
            session = await store.get_or_create(
                ADAPTER_ID, msg.chat_id, msg.sender_open_id or msg.sender_id or "anon"
            )
            stream = orch.reply(session, msg.text)
            await asyncio.wait_for(
                _consume_events_to_card(stream, ch, card_id, msg.chat_id),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            logger.warning("orchestrator_timeout", sender=msg.sender_id)
            err = "处理超时,请稍后重试。"
            if card_id:
                try:
                    await ch.update_card(card_id, err)
                except Exception:
                    pass
        except Exception as e:
            logger.exception("orchestrator_callback_failed", error=str(e)[:200])
            err = f"抱歉,处理请求时出错:{e}"
            if card_id:
                await ch.update_card(card_id, err)
            else:
                await ch.send_message(msg.chat_id, err)
        finally:
            channel_runner._current_platform.reset(token_platform)
            channel_runner._current_sender_open_id.reset(token_sender)
            channel_runner._current_chat_id.reset(token_chat)
            channel_runner._thinking_card_msg_id.reset(token_card)
        return ""

    ch._ws_stop = stop
    await ch.start(agent_cb=callback)
    logger.info("ws_started", msg="飞书双轨 demo (DefaultOrchestrator) 已启动")
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop.set())
    await stop.wait()
    await ch.stop()
    logger.info("ws_stopped")


if __name__ == "__main__":
    asyncio.run(main())
