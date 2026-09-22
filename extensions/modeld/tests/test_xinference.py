"""Xinference 探测分类契约。

探测方式是打一次 max_tokens=1 的最小补全——只有它才能回答"现在能不能用"。
注意：/v1/models 里列出模型 ≠ 可用，加载中也会被列出（今天实测过）。
"""

from __future__ import annotations

from app.xinference import ModelStatus, classify_probe


def test_ready_on_200():
    s = classify_probe(200, '{"choices":[]}')
    assert s.state == "ready"
    assert s.usable is True


def test_loading_on_launching_message():
    """实测原文：Model Qwen3.8-27B is launching, not yet ready for inference"""
    s = classify_probe(
        400,
        '{"detail":"Model is loading, please retry later: Model Qwen3.8-27B is launching, not yet ready for inference"}',
    )
    assert s.state == "loading"
    assert s.usable is False


def test_loading_on_503():
    assert classify_probe(503, "").state == "loading"


def test_down_when_unreachable():
    s = classify_probe(None, "")
    assert s.state == "down"
    assert s.usable is False


def test_down_on_unexpected_error():
    s = classify_probe(500, "boom")
    assert s.state == "down"
    assert "500" in s.detail


def test_usable_only_when_ready():
    assert ModelStatus(state="loading", detail="", ).usable is False
