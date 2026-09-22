"""ConversationEngine 的 System-1 验证钩子契约。

设计约束：
- `on_verify` 不传 → 行为与改动前**逐条一致**（向后兼容是硬要求）
- 判定失败 / 钩子抛异常 → **fail-open**，直接返回原回答（判定不能阻塞主流程）
- 判不可信 → 带反馈重试（把 Jev 判定回注 prompt，同模型重生）
- 重试用尽 → 返回最后候选，**不报错**（输出永远优于报错）
- 重试消耗 max_iterations（默认只有 5），所以上限必须小
"""

from __future__ import annotations

import pytest

from openagentic.agent import engine as eng


class _Verdict:
    def __init__(self, passed: bool, feedback_prompt: str = ""):
        self.passed = passed
        self.feedback_prompt = feedback_prompt


def _resp(content: str) -> dict:
    return {"message": {"role": "assistant", "content": content, "tool_calls": [], "thinking": ""}}


@pytest.fixture
def calls(monkeypatch):
    """记录每轮实际发给模型的 messages。"""
    seen: list[list[str]] = []

    async def fake_chat(messages, model, api_base, api_key, tools=None):
        seen.append([str(m.get("content")) for m in messages])
        return _resp(f"回答{len(seen)}")

    monkeypatch.setattr(eng, "litellm_chat", fake_chat)
    return seen


USER_MSG = [{"role": "user", "content": "hi"}]


async def test_no_hook_returns_directly(calls):
    """不传 on_verify → 与从前完全一致：一次调用、直接返回。"""
    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="")
    out = await e.chat(list(USER_MSG))
    assert out == "回答1"
    assert len(calls) == 1


async def test_hook_receives_content(calls):
    got: list[str] = []

    async def on_verify(content, messages):
        got.append(content)
        return _Verdict(True)

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify)
    out = await e.chat(list(USER_MSG))
    assert out == "回答1"
    assert got == ["回答1"]
    assert len(calls) == 1


async def test_failed_verdict_triggers_feedback_retry(calls):
    verdicts = [_Verdict(False, "请重做：上一次答非所问"), _Verdict(True)]

    async def on_verify(content, messages):
        return verdicts.pop(0)

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify,
                               max_verify_retries=1)
    out = await e.chat(list(USER_MSG))
    assert out == "回答2", "应带反馈重生一次"
    assert len(calls) == 2
    assert any("请重做" in c for c in calls[1]), "反馈提示行必须进了上下文"


async def test_retries_exhausted_returns_last_candidate(calls):
    """重试用尽返回最后候选，不报错——输出永远优于报错。"""

    async def on_verify(content, messages):
        return _Verdict(False, "请重做")

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify,
                               max_verify_retries=1)
    out = await e.chat(list(USER_MSG))
    assert out == "回答2"
    assert len(calls) == 2, "不该无限重试"


async def test_hook_returning_none_fails_open(calls):
    async def on_verify(content, messages):
        return None

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify)
    out = await e.chat(list(USER_MSG))
    assert out == "回答1"
    assert len(calls) == 1


async def test_hook_raising_fails_open(calls):
    """判定器抛异常不能把整个对话搞挂。"""

    async def on_verify(content, messages):
        raise RuntimeError("jev down")

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify)
    out = await e.chat(list(USER_MSG))
    assert out == "回答1"
    assert len(calls) == 1


async def test_retry_does_not_exceed_iteration_budget(calls):
    """重试消耗 max_iterations（默认 5）——上限小才不会把请求耗死。"""

    async def on_verify(content, messages):
        return _Verdict(False, "再改")

    e = eng.ConversationEngine(model="m", api_key="k", tools=[], system_prompt="", on_verify=on_verify,
                               max_verify_retries=99, max_iterations=5)
    out = await e.chat(list(USER_MSG))
    assert len(calls) <= 5
    assert out.startswith("回答")
