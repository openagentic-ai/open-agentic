"""DefaultOrchestrator 流式事件测试。

mock litellm_chat,验证三种典型路径下事件序列正确:
1. 纯文本回复 → thinking(启动) + thinking(轮 1) + final
2. 工具调用一次后回复 → ... + tool_call + tool_result + ... + final
3. LLM 抛异常 → error
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from openagentic.application import (
    DefaultOrchestrator,
    DefaultToolRegistry,
    ErrorEvent,
    FinalEvent,
    Session,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolSpec,
)


def _make_orchestrator(*, registry: DefaultToolRegistry | None = None) -> DefaultOrchestrator:
    return DefaultOrchestrator(
        model="mock/dummy",
        api_key="sk-test",
        api_base=None,
        system_prompt="you are test bot",
        tool_registry=registry or DefaultToolRegistry(),
        enable_memory=False,  # 避开 MemoryManager 文件 IO
    )


def _make_session(adapter_id: str = "test") -> Session:
    return Session(
        session_id="sid-1",
        adapter_id=adapter_id,
        external_session_id="ext-1",
        user_id="user-1",
    )


async def _collect(stream) -> list:
    out = []
    async for ev in stream:
        out.append(ev)
    return out


# ── 路径 1: 纯文本 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pure_text_reply():
    async def fake_litellm_chat(**kwargs: Any) -> dict:
        return {"message": {"content": "hello world", "tool_calls": []}}

    orch = _make_orchestrator()
    session = _make_session()

    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        events = await _collect(orch.reply(session, "hi"))

    # 事件序列: 启动 thinking + 轮1 thinking + final
    assert any(isinstance(e, ThinkingEvent) for e in events)
    assert any(isinstance(e, FinalEvent) and e.text == "hello world" for e in events)
    # seq 单调递增
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    # session_id 一致
    assert all(e.session_id == "sid-1" for e in events)


# ── 路径 2: 工具调用一次后回复 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_call_then_reply():
    call_count = {"n": 0}

    async def fake_litellm_chat(**kwargs: Any) -> dict:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"message": {
                "content": "",
                "tool_calls": [{
                    "id": "tc1",
                    "function": {"name": "echo", "arguments": '{"text": "hi"}'},
                }],
            }}
        return {"message": {"content": "工具回 hi", "tool_calls": []}}

    async def echo_handler(text: str = "") -> str:
        return f"echoed:{text}"

    registry = DefaultToolRegistry()
    registry.register_global(ToolSpec(
        name="echo",
        description="echo back",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=echo_handler,
    ))

    orch = _make_orchestrator(registry=registry)
    session = _make_session()

    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        events = await _collect(orch.reply(session, "请回声 hi"))

    tool_call_evs = [e for e in events if isinstance(e, ToolCallEvent)]
    tool_res_evs = [e for e in events if isinstance(e, ToolResultEvent)]
    final_evs = [e for e in events if isinstance(e, FinalEvent)]

    assert len(tool_call_evs) == 1
    assert tool_call_evs[0].tool_name == "echo"
    assert tool_call_evs[0].tool_args == {"text": "hi"}
    assert tool_call_evs[0].call_id == "tc1"

    assert len(tool_res_evs) == 1
    assert tool_res_evs[0].call_id == "tc1"
    assert tool_res_evs[0].result == "echoed:hi"
    assert tool_res_evs[0].error is None

    assert len(final_evs) == 1
    assert final_evs[0].text == "工具回 hi"

    # tool_call 一定在 tool_result 之前
    tc_seq = tool_call_evs[0].seq
    tr_seq = tool_res_evs[0].seq
    final_seq = final_evs[0].seq
    assert tc_seq < tr_seq < final_seq


# ── 路径 3: LLM 抛异常 → ErrorEvent ─────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_exception_yields_error_event():
    async def fake_litellm_chat(**kwargs: Any) -> dict:
        raise RuntimeError("LLM down")

    orch = _make_orchestrator()
    session = _make_session()

    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        events = await _collect(orch.reply(session, "hi"))

    error_evs = [e for e in events if isinstance(e, ErrorEvent)]
    final_evs = [e for e in events if isinstance(e, FinalEvent)]
    assert len(error_evs) == 1
    assert error_evs[0].code == "chat_failed"
    assert "LLM down" in error_evs[0].message
    assert final_evs == []  # 异常路径不发 final


# ── 路径 4: history 持久化 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_persists_after_final():
    async def fake_litellm_chat(**kwargs: Any) -> dict:
        return {"message": {"content": "ok", "tool_calls": []}}

    orch = _make_orchestrator()
    session = _make_session()

    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        await _collect(orch.reply(session, "first"))
        await _collect(orch.reply(session, "second"))

    history = orch._histories["sid-1"]
    # 两轮 = 4 条(user/assistant ×2)
    assert len(history) == 4
    assert history[0] == {"role": "user", "content": "first"}
    assert history[1] == {"role": "assistant", "content": "ok"}
    assert history[2] == {"role": "user", "content": "second"}
    assert history[3] == {"role": "assistant", "content": "ok"}


# ── 路径 5: error 不污染 history ────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_does_not_pollute_history():
    async def fake_litellm_chat(**kwargs: Any) -> dict:
        raise RuntimeError("boom")

    orch = _make_orchestrator()
    session = _make_session()

    with patch("openagentic.agent.engine.litellm_chat", side_effect=fake_litellm_chat):
        await _collect(orch.reply(session, "fail me"))

    assert orch._histories.get("sid-1", []) == []
