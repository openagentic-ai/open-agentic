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


# --- 升级兜底（本地后端不可用 → 转云端）--------------------------------

YAML_ESCALATION = """
tiers:
  local:
    gate_category: llm_local
    concurrency: 2
    endpoints:
      - "127.0.0.1:9997"
escalation:
  enabled: true
  target_model: "deepseek/deepseek-v4-flash"
"""


class _FakeStore:
    """替身：把升级目标解析成云端的 (model, api_base, api_key)。"""

    def resolve_runtime(self, model):
        return ("openai/deepseek-v4-flash", "https://api.deepseek.com/v1", "cloud-key")


@pytest.fixture
def escalation_env(monkeypatch, tmp_path):
    cp = tmp_path / "cp.yaml"
    cp.write_text(YAML_ESCALATION, encoding="utf-8")
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(cp))
    monkeypatch.setattr(
        "openagentic.core.llm.provider_config.get_provider_store", lambda: _FakeStore()
    )
    return cp


def _failing_local(record: list):
    async def _acompletion(**kwargs):
        record.append((kwargs["model"], kwargs.get("api_base")))
        if "9997" in str(kwargs.get("api_base")):
            raise RuntimeError("connection refused")
        return _Resp()

    return _acompletion


async def test_escalates_to_cloud_when_local_fails(monkeypatch, gate, escalation_env):
    """本地挂 → 自动转云端，调用方拿到的是云端结果。"""
    calls: list = []
    monkeypatch.setattr(litellm, "acompletion", _failing_local(calls))

    out = await litellm_chat(
        messages=[{"role": "user", "content": "hi"}],
        model="openai/Qwen3.8-27B",
        api_base="http://127.0.0.1:9997/v1",
        api_key="k",
    )

    assert out["message"]["content"] == "ok"
    assert len(calls) == 2
    assert "9997" in str(calls[0][1])
    assert "deepseek" in str(calls[1][1])


async def test_no_escalation_when_disabled(monkeypatch, gate, tmp_path):
    """未启用升级 → 异常原样抛出，行为与从前一致。"""
    cp = tmp_path / "cp.yaml"
    cp.write_text(YAML, encoding="utf-8")  # YAML 里 escalation.enabled = false
    monkeypatch.setenv("OPENAGENTIC_CONTROL_PLANE_CONFIG", str(cp))

    calls: list = []
    monkeypatch.setattr(litellm, "acompletion", _failing_local(calls))

    with pytest.raises(RuntimeError, match="connection refused"):
        await litellm_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/Qwen3.8-27B",
            api_base="http://127.0.0.1:9997/v1",
            api_key="k",
        )
    assert len(calls) == 1


async def test_raises_original_error_when_escalation_also_fails(
    monkeypatch, gate, escalation_env
):
    """升级也失败 → 抛原始错误，不掩盖本地故障的真因。"""
    calls: list = []

    async def _both_fail(**kwargs):
        calls.append((kwargs["model"], kwargs.get("api_base")))
        raise RuntimeError("connection refused" if "9997" in str(kwargs.get("api_base")) else "cloud 503")

    monkeypatch.setattr(litellm, "acompletion", _both_fail)

    with pytest.raises(RuntimeError, match="connection refused"):
        await litellm_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/Qwen3.8-27B",
            api_base="http://127.0.0.1:9997/v1",
            api_key="k",
        )
    assert len(calls) == 2
