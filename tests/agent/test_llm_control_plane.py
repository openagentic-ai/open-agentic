"""litellm_chat 与控制面的接线契约：

1. 控制面未启用 → 走原有 "llm" 类别（现有行为零变化）
2. 控制面启用 + 本地端点 → 走 "llm_local" 类别
3. 控制面启用 + 云端端点 → 仍走 "llm"
"""

from __future__ import annotations

contextlib_cm = __import__("contextlib")

import pytest

import litellm
from openagentic.agent.llm import litellm_chat


class _RecordingGate:
    """记录 acquire 到的类别，不做实际限流。"""

    def __init__(self) -> None:
        self.categories: list[str] = []

    def acquire(self, category: str = "default"):
        self.categories.append(category)

        @contextlib_cm.asynccontextmanager
        async def _cm():
            yield

        return _cm()


class _Msg:
    role = "assistant"
    content = "ok"
    tool_calls = None
    thinking = None


class _Choice:
    message = _Msg()


class _Resp:
    choices = [_Choice()]


async def _fake_acompletion(**kwargs):
    return _Resp()


YAML = """
tiers:
  local:
    gate_category: llm_local
    concurrency: 2
    endpoints:
      - "127.0.0.1:9997"
  cloud:
    gate_category: llm
    concurrency: 30
escalation:
  enabled: false
  target_model: ""
"""


@pytest.fixture
def gate(monkeypatch):
    g = _RecordingGate()
    monkeypatch.setattr("openagentic.concurrency.get_default_gate", lambda: g)
    monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)
    return g


async def test_defaults_to_llm_when_control_plane_off(monkeypatch, gate, tmp_path):
    """未配置控制面 → 完全维持原行为。"""
    monkeypatch.delenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", raising=False)
    await litellm_chat(
        messages=[{"role": "user", "content": "hi"}],
        model="openai/Qwen3.8-27B",
        api_base="http://127.0.0.1:9997/v1",
        api_key="k",
    )
    assert gate.categories == ["llm"]


async def test_uses_local_category_for_local_endpoint(monkeypatch, gate, tmp_path):
    cp = tmp_path / "cp.yaml"
    cp.write_text(YAML, encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(cp))

    await litellm_chat(
        messages=[{"role": "user", "content": "hi"}],
        model="openai/Qwen3.8-27B",
        api_base="http://127.0.0.1:9997/v1",
        api_key="k",
    )
    assert gate.categories == ["llm_local"]


async def test_uses_llm_category_for_cloud_endpoint(monkeypatch, gate, tmp_path):
    cp = tmp_path / "cp.yaml"
    cp.write_text(YAML, encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(cp))

    await litellm_chat(
        messages=[{"role": "user", "content": "hi"}],
        model="openai/deepseek-v4-flash",
        api_base="https://api.deepseek.com/v1",
        api_key="k",
    )
    assert gate.categories == ["llm"]
