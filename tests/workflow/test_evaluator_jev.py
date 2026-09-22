"""evaluator 接 Jev 的契约。

现状：让 LLM 自由打分（{score, feedback}），贵、不校准、不可复现。
改为优先走 Jev 的封闭判定（noul = 是否满足标准的校准概率），
Jev 不可用或失败时**回落到原有 LLM 路径**，接口语义不变（min_score / passed / feedback）。
"""

from __future__ import annotations

import pytest

from openagentic.control_plane import system1 as _s1
from openagentic.workflow import evaluator as ev


class _FakeJev:
    def __init__(self, answers=None, fail=False):
        self._answers = answers
        self.fail = fail
        self.calls = 0

    def ask(self, state, questions, max_retries=None):
        self.calls += 1
        if self.fail:
            raise OSError("jev down")
        return self._answers


ANSWERS = {
    "meets": {"type": "noul", "noul": 0.88, "confidence": 0.91},
    "quality": {"type": "choice", "choice": "good", "confidence": 0.8},
}


@pytest.fixture
def jev_ready(monkeypatch):
    fake = _FakeJev(ANSWERS)
    monkeypatch.setattr(_s1, "build_jev", lambda: fake)
    return fake


async def test_uses_jev_when_available(jev_ready):
    r = await ev.execute_evaluator(target_output="写得很好的答案", criteria="必须切题", min_score=0.7)
    assert r["score"] == pytest.approx(0.88)
    assert r["passed"] is True
    assert "Jev" in r["feedback"]
    assert jev_ready.calls == 1


async def test_jev_below_threshold_fails(monkeypatch):
    monkeypatch.setattr(_s1, "build_jev", lambda: _FakeJev({
        "meets": {"type": "noul", "noul": 0.3, "confidence": 0.9},
        "quality": {"type": "choice", "choice": "poor", "confidence": 0.9},
    }))
    r = await ev.execute_evaluator(target_output="答非所问", criteria="必须切题", min_score=0.7)
    assert r["passed"] is False
    assert r["score"] == pytest.approx(0.3)


async def test_falls_back_to_llm_when_jev_absent(monkeypatch):
    monkeypatch.setattr(_s1, "build_jev", lambda: None)
    called = {}

    async def _fake_chat(messages, model, api_base, api_key, tools=None):
        called["hit"] = True
        return {"message": {"content": '{"score": 0.75, "feedback": "还行"}'}}

    monkeypatch.setattr(ev, "litellm_chat", _fake_chat, raising=False)
    r = await ev.execute_evaluator(target_output="x", criteria="y", min_score=0.7)
    assert called.get("hit") is True
    assert r["score"] == pytest.approx(0.75)


async def test_falls_back_to_llm_when_jev_raises(monkeypatch):
    """Jev 抛异常不能让评估整个失败——宽容策略：回落 LLM。"""
    monkeypatch.setattr(_s1, "build_jev", lambda: _FakeJev(fail=True))
    called = {}

    async def _fake_chat(messages, model, api_base, api_key, tools=None):
        called["hit"] = True
        return {"message": {"content": '{"score": 0.6, "feedback": "ok"}'}}

    monkeypatch.setattr(ev, "litellm_chat", _fake_chat, raising=False)
    r = await ev.execute_evaluator(target_output="x", criteria="y", min_score=0.5)
    assert called.get("hit") is True
    assert r["passed"] is True
