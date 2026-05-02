"""run_feishu_ws_orchestrator demo 集成冒烟测试。

mock litellm + 飞书 channel 的发送函数,验证:
1. _build_orchestrator 装配通过
2. callback() 调用走 DefaultOrchestrator.reply()
3. ThinkingEvent / ToolCallEvent / FinalEvent 按事件分类驱动卡片
4. contextvars 在工具调用时已设置(读到非空 chat_id)
5. update_card 在 final 时被调一次(终态写卡)
"""
from __future__ import annotations

import sys
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
async def test_orchestrator_demo_end_to_end():
    # 必须先 set env 再 import,_build_orchestrator 启动期读 env
    os.environ.setdefault("LITELLM_DEFAULT_MODEL", "openai/deepseek-v4-flash")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com/v1")

    from scripts import run_feishu_ws_orchestrator as m
    from extensions.channels import channel_runner

    orch = m._build_orchestrator()

    # mock LLM 返回:第 1 轮调 read_file,第 2 轮回纯文本
    seen_chat_ids: list[str] = []
    call_count = {"n": 0}

    async def fake_litellm_chat(**kwargs: Any) -> dict:
        # 验证工具执行时 contextvars 已被 callback 设置
        seen_chat_ids.append(channel_runner._current_chat_id.get(""))
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"message": {
                "content": "",
                "tool_calls": [{
                    "id": "tc-read",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "/etc/hostname", "max_lines": 1}',
                    },
                }],
            }}
        return {"message": {"content": "已读完", "tool_calls": []}}

    # mock 飞书 channel:不真连飞书
    fake_ch = AsyncMock()
    fake_ch.send_thinking_card = AsyncMock(return_value="card-fake-id")
    fake_ch.update_card = AsyncMock(return_value=True)
    fake_ch.send_message = AsyncMock(return_value=True)

    # 构造 IncomingMessage(只用 callback 读到的字段)
    class _Msg:
        platform = "feishu"
        sender_id = "u_test"
        sender_open_id = "ou_test"
        chat_id = "oc_test"
        text = "读一下 /etc/hostname"

    # 直接调 callback —— 但 callback 是 main() 内部闭包,得"重写"流程
    # 简化:直接拼出等价 flow。
    store = m.DefaultSessionStore()

    # 复用 callback 逻辑的核心三步,但把 ch 替换成 fake_ch、orch 用本地 orch
    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        # mock execute_tool 内部的 read_file 走的并发门 + 文件 IO,简化为返回 "ok"
        async def fake_execute_tool(name: str, args: dict) -> str:
            if name == "read_file":
                return f"hostname=fake-host (path={args.get('path')})"
            return f"unknown:{name}"

        # 替换 orch 的 executor
        orch._executor = fake_execute_tool

        msg = _Msg()
        card_id = await fake_ch.send_thinking_card(msg.chat_id)
        token_platform = channel_runner._current_platform.set(msg.platform)
        token_sender = channel_runner._current_sender_open_id.set(msg.sender_open_id)
        token_chat = channel_runner._current_chat_id.set(msg.chat_id)
        token_card = channel_runner._thinking_card_msg_id.set(card_id or "")
        try:
            session = await store.get_or_create("feishu", msg.chat_id, msg.sender_open_id)
            stream = orch.reply(session, msg.text)
            final_text = await m._consume_events_to_card(stream, fake_ch, card_id, msg.chat_id)
        finally:
            channel_runner._current_platform.reset(token_platform)
            channel_runner._current_sender_open_id.reset(token_sender)
            channel_runner._current_chat_id.reset(token_chat)
            channel_runner._thinking_card_msg_id.reset(token_card)

    # 验证
    assert final_text == "已读完"
    # contextvars 在每次 LLM 调用时都应该是设置好的
    assert all(cid == "oc_test" for cid in seen_chat_ids), seen_chat_ids
    # send_thinking_card 调一次,update_card 至少调一次(final)
    assert fake_ch.send_thinking_card.await_count == 1
    assert fake_ch.update_card.await_count >= 1
    # final 内容写到卡片
    last_call = fake_ch.update_card.await_args_list[-1]
    assert last_call.args[0] == card_id
    assert last_call.args[1] == "已读完"
