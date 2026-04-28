"""Phase 7 Sub-milestone 1.1：suspended 状态与挂起信号槽 helper 的纯 Python 测试。

只覆盖：
- ExecutionStatus 枚举包含 suspended
- TERMINAL_STATUSES 不含 suspended（可逆状态）
- set_/get_/clear_waiting_for 与 set_/pop_resume_payload 的 round-trip
- 信号槽校验（必需键缺失抛 ValueError；非 dict 抛 TypeError）

不涉及 DB / runtime / channels（那些是 1.2 / 1.3 / 1.4 的事）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from openagentic.workflow import service
from openagentic.workflow.models import TERMINAL_STATUSES, ExecutionStatus


def _make_run(node_states: dict | None = None) -> SimpleNamespace:
    """构造一个最小 run 对象（不依赖 SQLAlchemy）。"""
    return SimpleNamespace(node_states=node_states or {})


# ---------- 枚举 ----------


def test_execution_status_has_suspended():
    assert ExecutionStatus.suspended.value == "suspended"


def test_terminal_statuses_excludes_suspended_and_running():
    assert ExecutionStatus.suspended not in TERMINAL_STATUSES
    assert ExecutionStatus.running not in TERMINAL_STATUSES
    assert ExecutionStatus.pending not in TERMINAL_STATUSES
    assert ExecutionStatus.completed in TERMINAL_STATUSES
    assert ExecutionStatus.failed in TERMINAL_STATUSES
    assert ExecutionStatus.cancelled in TERMINAL_STATUSES


# ---------- waiting_for 信号槽 ----------


def test_get_waiting_for_returns_none_when_absent():
    run = _make_run()
    assert service.get_waiting_for(run) is None


def test_get_waiting_for_ignores_non_dict():
    run = _make_run({service.WAITING_FOR_KEY: "not-a-dict"})
    assert service.get_waiting_for(run) is None


def test_set_waiting_for_round_trip():
    run = _make_run({"trace": []})
    signal = {"type": "feishu_approval", "instance_key": "RECabc", "node_id": "approve"}
    service.set_waiting_for(run, signal)

    # 原 trace 不被破坏
    assert run.node_states["trace"] == []
    # 信号槽已写入
    got = service.get_waiting_for(run)
    assert got == signal


def test_set_waiting_for_rejects_non_dict():
    run = _make_run()
    with pytest.raises(TypeError):
        service.set_waiting_for(run, "oops")  # type: ignore[arg-type]


def test_set_waiting_for_requires_keys():
    run = _make_run()
    with pytest.raises(ValueError, match="missing keys"):
        service.set_waiting_for(run, {"type": "feishu_approval"})


def test_clear_waiting_for_returns_signal_and_removes_key():
    run = _make_run()
    signal = {"type": "feishu_approval", "instance_key": "RECabc", "node_id": "approve"}
    service.set_waiting_for(run, signal)

    got = service.clear_waiting_for(run)
    assert got == signal
    assert service.WAITING_FOR_KEY not in run.node_states
    # 第二次 clear 返回 None
    assert service.clear_waiting_for(run) is None


# ---------- resume 载荷 ----------


def test_resume_payload_round_trip():
    run = _make_run()
    payload = {"approved": True, "reason": "ok"}
    service.set_resume_payload(run, payload)

    got = service.pop_resume_payload(run)
    assert got == payload
    assert service.RESUME_PAYLOAD_KEY not in run.node_states
    # 第二次 pop 返回 None
    assert service.pop_resume_payload(run) is None


def test_set_resume_payload_rejects_non_dict():
    run = _make_run()
    with pytest.raises(TypeError):
        service.set_resume_payload(run, ["nope"])  # type: ignore[arg-type]


def test_waiting_and_resume_coexist():
    """挂起信号槽与 resume 载荷可同时存在（resume 接口写 payload 后，runtime 才唤醒并消费）。"""
    run = _make_run()
    service.set_waiting_for(
        run, {"type": "human_input", "instance_key": "card-1", "node_id": "ask"}
    )
    service.set_resume_payload(run, {"text": "用户回答"})

    assert service.get_waiting_for(run) is not None
    assert service.pop_resume_payload(run) == {"text": "用户回答"}
    # waiting_for 仍存在（由 runtime 在 1.2 阶段决定何时清）
    assert service.get_waiting_for(run) is not None
