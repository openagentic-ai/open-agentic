"""Jev 客户端契约。

Jev = 封闭选项判断（choice/score/noul），返回带 confidence 的完整概率分布。
与控制面其余部分一样：环境变量激活，未配置则整体不启用、行为与从前一致。

零第三方依赖（urllib），可注入 opener 便于单测。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openagentic.control_plane.jev import JevClient, build_jev, jev_enabled


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeOpener:
    """记录请求，返回预设响应。"""

    def __init__(self, payload=None, fail=False):
        self.calls = 0
        self._payload = payload or {"answers": {"meets": {"type": "noul", "noul": 0.87}}}
        self._fail = fail

    def open(self, req, timeout=None):
        self.calls += 1
        if self._fail:
            raise OSError("connection refused")
        return _FakeResponse(self._payload)


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "logs"


# --- 激活开关 ---------------------------------------------------------

def test_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv("OPENAGENTIC_JEV_ENABLED", raising=False)
    assert jev_enabled() is False
    assert build_jev() is None


def test_disabled_when_no_key(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_JEV_ENABLED", "1")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert build_jev() is None


def test_enabled_with_key(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_JEV_ENABLED", "1")
    monkeypatch.setenv("JEV_API_KEY", "k-123")
    assert jev_enabled() is True
    assert isinstance(build_jev(cache_dir="/tmp"), JevClient)


def test_typesafe_key_is_accepted_as_fallback(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_JEV_ENABLED", "1")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-123")
    assert isinstance(build_jev(cache_dir="/tmp"), JevClient)


# --- 调用 -------------------------------------------------------------

def test_ask_posts_and_parses(cache_dir):
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    ans = c.ask(state={"a": 1}, questions={"meets": {"type": "noul"}})
    assert ans == {"meets": {"type": "noul", "noul": 0.87}}
    assert op.calls == 1


def test_ask_caches_identical_payload(cache_dir):
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    q = {"meets": {"type": "noul"}}
    c.ask(state={"a": 1}, questions=q)
    c.ask(state={"a": 1}, questions=q)
    assert op.calls == 1, "相同 payload 不应重复打网络"


def test_ask_different_payload_not_cached(cache_dir):
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    c.ask(state={"a": 1}, questions={"meets": {"type": "noul"}})
    c.ask(state={"a": 2}, questions={"meets": {"type": "noul"}})
    assert op.calls == 2


def test_ask_returns_none_on_failure(cache_dir):
    op = _FakeOpener(fail=True)
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op,
                  max_retries=2)
    assert c.ask(state={"a": 1}, questions={"meets": {"type": "noul"}}) is None


def test_ask_returns_none_without_key(cache_dir):
    c = JevClient(base="https://api.example", key="", cache_dir=cache_dir, opener=_FakeOpener())
    assert c.ask(state={"a": 1}, questions={"meets": {"type": "noul"}}) is None


def test_ask_writes_cost_ledger(cache_dir):
    op = _FakeOpener({"answers": {"meets": {"noul": 0.5}}, "usage": {"input_tokens": 10}})
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    c.ask(state={"a": 1}, questions={"meets": {"type": "noul"}})
    ledger = cache_dir / "jev_log.jsonl"
    assert ledger.exists()
    assert "input_tokens" in ledger.read_text(encoding="utf-8")


# --- 输入截断 ---------------------------------------------------------

def test_long_string_is_truncated(cache_dir, monkeypatch):
    """RLCD 模型窗口很小，超长输入必须截断，否则可能整条判定失效。"""
    monkeypatch.setenv("JEV_MAX_OUTPUT_CHARS", "100")
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    captured = {}

    def _capture(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _FakeResponse({"answers": {"meets": {"noul": 0.5}}})

    op.open = _capture
    c.ask(state={"output": "甲" * 500}, questions={"meets": {"type": "noul"}})

    sent = captured["body"]["state"]["output"]
    assert len(sent) < 500, "没截断"
    assert "省略" in sent, "缺省略标记"
    assert sent.startswith("甲") and sent.endswith("甲"), "应保留头尾"


def test_short_string_untouched(cache_dir, monkeypatch):
    monkeypatch.setenv("JEV_MAX_OUTPUT_CHARS", "10000")
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    captured = {}

    def _capture(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _FakeResponse({"answers": {"meets": {"noul": 0.5}}})

    op.open = _capture
    c.ask(state={"output": "短文本"}, questions={"meets": {"type": "noul"}})
    assert captured["body"]["state"]["output"] == "短文本"


def test_nested_state_strings_also_truncated(cache_dir, monkeypatch):
    """截断是边界防护，不该只认顶层 output 字段。"""
    monkeypatch.setenv("JEV_MAX_OUTPUT_CHARS", "50")
    op = _FakeOpener()
    c = JevClient(base="https://api.example", key="k", cache_dir=cache_dir, opener=op)
    captured = {}

    def _capture(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _FakeResponse({"answers": {"x": {"noul": 0.5}}})

    op.open = _capture
    c.ask(state={"a": {"b": "乙" * 300}}, questions={"x": {"type": "noul"}})
    assert len(captured["body"]["state"]["a"]["b"]) < 300
