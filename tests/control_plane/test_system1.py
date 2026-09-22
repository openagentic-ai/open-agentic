"""System-1 门面契约。

System-1 = RLCD 判定模型（Jev）：非自回归、只做封闭选项判断、给校准概率、不生成文本。
所以 feedback 必须从 choice 标签**合成**，不能让模型写。

三条判定各自独立：验证（必用）/ 路由（默认关）/ 信息够不够（默认关，引擎层暂无检索）。
Jev 未配置或失败一律返回 None，调用方回落——判定失败绝不阻塞主流程。
"""

from __future__ import annotations

import pytest

from openagentic.control_plane import system1 as s1


class _FakeJev:
    def __init__(self, answers=None, fail=False):
        self._answers = answers
        self.fail = fail
        self.calls: list[dict] = []

    def ask(self, state, questions, max_retries=None):
        self.calls.append({"state": state, "questions": questions})
        if self.fail:
            raise OSError("jev down")
        return self._answers


# --- 分级触发（纯函数）------------------------------------------------

def test_trigger_off_never_verifies():
    assert s1.should_verify("随便什么", had_tool_calls=True, trigger="off") is False


def test_trigger_always_verifies():
    assert s1.should_verify("短", had_tool_calls=False, trigger="always") is True


def test_high_risk_verifies_after_tool_calls():
    assert s1.should_verify("短", had_tool_calls=True, trigger="high_risk") is True


def test_high_risk_verifies_long_output():
    assert s1.should_verify("长" * 900, had_tool_calls=False,
                            trigger="high_risk", high_risk_chars=800) is True


def test_high_risk_skips_plain_short_answer():
    """普通短问答直出——每次调用 Jev 要 +1 秒且计费。"""
    assert s1.should_verify("好的", had_tool_calls=False,
                            trigger="high_risk", high_risk_chars=800) is False


# --- 验证/打分 --------------------------------------------------------

ANSWERS_OK = {
    "meets": {"type": "noul", "noul": 0.91, "confidence": 0.88},
    "quality": {"type": "choice", "choice": "good", "confidence": 0.8},
}
ANSWERS_BAD = {
    "meets": {"type": "noul", "noul": 0.22, "confidence": 0.9},
    "quality": {"type": "choice", "choice": "poor", "confidence": 0.9},
}


async def test_verify_passes_above_threshold():
    v = await s1.verify_output("好答案", "必须切题", min_score=0.7, jev=_FakeJev(ANSWERS_OK))
    assert v is not None
    assert v.passed is True
    assert v.score == pytest.approx(0.91)
    assert "Jev" in v.feedback


async def test_verify_fails_below_threshold():
    v = await s1.verify_output("烂答案", "必须切题", min_score=0.7, jev=_FakeJev(ANSWERS_BAD))
    assert v is not None
    assert v.passed is False
    assert v.score == pytest.approx(0.22)


async def test_failed_verdict_carries_prompt_for_retry():
    """不可信时要能带反馈重想——反馈提示行必须非空且含判据。"""
    v = await s1.verify_output("烂答案", "必须切题", min_score=0.7, jev=_FakeJev(ANSWERS_BAD))
    assert v.passed is False
    assert v.feedback_prompt
    assert "必须切题" in v.feedback_prompt


async def test_verify_returns_none_when_jev_absent():
    assert await s1.verify_output("x", "y", jev=None) is None


async def test_verify_returns_none_when_jev_raises():
    assert await s1.verify_output("x", "y", jev=_FakeJev(fail=True)) is None


async def test_verify_returns_none_on_empty_answers():
    assert await s1.verify_output("x", "y", jev=_FakeJev({})) is None


async def test_verify_returns_none_on_garbage_score():
    bad = {"meets": {"type": "noul", "noul": "不是数字"}}
    assert await s1.verify_output("x", "y", jev=_FakeJev(bad)) is None


# --- 路由 -------------------------------------------------------------

async def test_route_returns_choice():
    answers = {"route": {"type": "choice", "choice": "cloud", "confidence": 0.8}}
    assert await s1.route_message("帮我重构这段代码", jev=_FakeJev(answers)) == "cloud"


async def test_route_returns_none_when_absent():
    assert await s1.route_message("x", jev=None) is None


# --- 信息够不够 -------------------------------------------------------

async def test_sufficiency_true_when_enough():
    answers = {"enough": {"type": "noul", "noul": 0.85}}
    assert await s1.judge_sufficient("问题", "上下文", jev=_FakeJev(answers)) is True


async def test_sufficiency_false_when_not_enough():
    answers = {"enough": {"type": "noul", "noul": 0.2}}
    assert await s1.judge_sufficient("问题", "上下文", jev=_FakeJev(answers)) is False


async def test_sufficiency_none_when_absent():
    assert await s1.judge_sufficient("q", "c", jev=None) is None


# --- 激活助手：把配置变成 on_verify 回调 ------------------------------

class _Cfg:
    def __init__(self, enabled=True, trigger="high_risk", high_risk_chars=800,
                 min_score=0.7, criteria="必须切题", max_retries=1):
        verify = type("V", (), {
            "enabled": enabled, "trigger": trigger, "high_risk_chars": high_risk_chars,
            "min_score": min_score, "criteria": criteria, "max_retries": max_retries,
        })()
        self.system1 = type("S", (), {"verify": verify})()


def test_build_hook_none_when_config_absent():
    """控制面未启用 → 不返回钩子，引擎行为与从前完全一致。"""
    assert s1.build_verify_hook(None) is None


def test_build_hook_none_when_disabled():
    assert s1.build_verify_hook(_Cfg(enabled=False)) is None


def test_build_hook_returns_callable_when_enabled():
    assert callable(s1.build_verify_hook(_Cfg(enabled=True)))


async def test_hook_skips_low_risk(monkeypatch):
    fake = _FakeJev(ANSWERS_BAD)
    monkeypatch.setattr(s1, "build_jev", lambda: fake)
    hook = s1.build_verify_hook(_Cfg(trigger="high_risk", high_risk_chars=800))
    r = await hook("短回答", [{"role": "user", "content": "hi"}])
    assert r is None, "低风险不该调 Jev"
    assert fake.calls == []


async def test_hook_verifies_when_tools_used(monkeypatch):
    fake = _FakeJev(ANSWERS_BAD)
    monkeypatch.setattr(s1, "build_jev", lambda: fake)
    hook = s1.build_verify_hook(_Cfg(trigger="high_risk", high_risk_chars=800))
    msgs = [{"role": "user", "content": "hi"}, {"role": "tool", "content": "文件已删"}]
    r = await hook("短回答", msgs)
    assert r is not None and r.passed is False
    assert len(fake.calls) == 1
