"""DefaultOrchestrator 端到端真实 LLM demo。

用法:
    cd /opt/open-agentic
    .venv/bin/python scripts/demo_orchestrator.py "今天几号?顺便算下 23*47"

依赖 .env 里的 OPENAI_API_KEY / OPENAI_BASE_URL / LITELLM_DEFAULT_MODEL。

目的: pytest 是 mock,这里证明 hooks/queue/异步桥接在真实 LLM 下不挂。
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# 让 src/ 上 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from openagentic.application import (  # noqa: E402
    DefaultOrchestrator,
    DefaultSessionStore,
    DefaultToolRegistry,
    ErrorEvent,
    FinalEvent,
    PartialEvent,
    Session,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolSpec,
)


# ── 演示工具:两个简单同步逻辑包成 async ──────────────────────────────

async def get_today(_: dict | None = None) -> str:
    return datetime.now().strftime("%Y-%m-%d %A")


async def calc(expression: str = "") -> str:
    """简易计算器(只允许数字和 +-*/() ,无 eval 注入风险)。"""
    allowed = set("0123456789+-*/(). ")
    if not expression or set(expression) - allowed:
        return f"非法表达式: {expression!r}"
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"计算失败: {exc}"


def _build_registry() -> DefaultToolRegistry:
    reg = DefaultToolRegistry()
    reg.register_global(ToolSpec(
        name="get_today",
        description="返回今天的日期(YYYY-MM-DD 加星期几)",
        parameters={"type": "object", "properties": {}},
        handler=get_today,
    ))
    reg.register_global(ToolSpec(
        name="calc",
        description="计算简单数学表达式,只支持 +-*/()",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        handler=calc,
    ))
    return reg


def _format_event(ev) -> str:
    base = f"[seq={ev.seq:>2}] {type(ev).__name__:<18}"
    if isinstance(ev, ThinkingEvent):
        return f"{base} {ev.text}"
    if isinstance(ev, PartialEvent):
        return f"{base} +{ev.delta!r}"
    if isinstance(ev, ToolCallEvent):
        return f"{base} {ev.tool_name}({ev.tool_args}) call_id={ev.call_id}"
    if isinstance(ev, ToolResultEvent):
        marker = " ERR" if ev.error else ""
        return f"{base}{marker} call_id={ev.call_id} -> {str(ev.result)[:120]}"
    if isinstance(ev, FinalEvent):
        return f"{base} {ev.text}"
    if isinstance(ev, ErrorEvent):
        return f"{base} [{ev.code}] {ev.message}"
    return f"{base} {ev}"


async def main() -> None:
    user_text = " ".join(sys.argv[1:]) or "今天几号?顺便算下 23*47"

    model = os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("OPENAGENTIC_MODEL") or ""
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_base = os.getenv("OPENAI_BASE_URL") if model.startswith("openai/") else None
    if not model or not api_key:
        print("缺 LITELLM_DEFAULT_MODEL / OPENAI_API_KEY,从 .env 读取失败", file=sys.stderr)
        sys.exit(2)

    print(f"model={model}  api_base={api_base}")
    print(f"user_text={user_text!r}\n")

    orch = DefaultOrchestrator(
        model=model,
        api_key=api_key,
        api_base=api_base,
        system_prompt=(
            "你是测试 bot。如果用户问日期就调 get_today;"
            "问算术就调 calc;否则直接回。回复用中文,简短。"
        ),
        tool_registry=_build_registry(),
        enable_memory=False,  # demo 不接 MemoryManager,避免外部依赖
    )

    store = DefaultSessionStore()
    session = await store.get_or_create("cli-demo", "demo-chat-1", "demo-user-1")

    print(f"session_id={session.session_id}\n")
    print("─── ReplyEvent 流 ───")
    final_seen = False
    async for ev in orch.reply(session, user_text):
        print(_format_event(ev))
        if isinstance(ev, FinalEvent):
            final_seen = True

    print()
    print("─── history 验证 ───")
    print(f"history 长度 = {len(orch._histories[session.session_id])}")
    print(f"final 事件出现 = {final_seen}")


if __name__ == "__main__":
    asyncio.run(main())
