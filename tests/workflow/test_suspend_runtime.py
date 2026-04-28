"""Phase 7 Sub-milestone 1.2：runtime 真把 run 置为 suspended 的行为测试。

覆盖：
- validate_definition 接受 approval / human_input
- _execute_node 对 approval / human_input 返回挂起信号
- _execute_definition 检测挂起信号 → set_waiting_for + 持久化 outputs/trace + return early
- execute_run 状态流转：pending → running → suspended
- execute_run 对 suspended run 不设 completed_at、不覆盖 node_states
- 挂起后后续节点不执行（break 验证）
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from openagentic.workflow import service
from openagentic.workflow.models import TERMINAL_STATUSES, ExecutionStatus


class DummyDB:
    """最小 fake DB：refresh 无操作，flush 记录调用次数。"""
    def __init__(self):
        self.flush_count = 0

    async def refresh(self, _run):
        return None

    async def flush(self):
        self.flush_count += 1


# ---------- validate_definition ----------


def test_validate_definition_accepts_approval_and_human_input():
    service.validate_definition({
        "nodes": [
            {"id": "start", "type": "value", "config": {"value": "go"}},
            {"id": "approve", "type": "approval", "config": {"channel": "feishu", "approval_code": "REC123"}},
            {"id": "ask", "type": "human_input", "config": {"channel": "feishu", "prompt": "请输入"}},
        ],
        "edges": [
            {"from": "start", "to": "approve"},
            {"from": "approve", "to": "ask"},
        ],
    })


def test_validate_definition_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unsupported node type"):
        service.validate_definition({
            "nodes": [{"id": "n1", "type": "unknown_type"}],
            "edges": [],
        })


# ---------- _execute_node 挂起信号 ----------


def test_execute_node_approval_returns_suspend_signal():
    result = asyncio.run(
        service._execute_node("approval", {"channel": "feishu", "approval_code": "RECabc"})
    )
    assert result[service.SUSPEND_FLAG] is True
    assert result["suspend_type"] == "approval"
    assert result["channel"] == "feishu"
    assert result["instance_key"] == "RECabc"


def test_execute_node_human_input_returns_suspend_signal():
    result = asyncio.run(
        service._execute_node("human_input", {"channel": "wecom", "prompt": "请回复", "instance_key": "card-1"})
    )
    assert result[service.SUSPEND_FLAG] is True
    assert result["suspend_type"] == "human_input"
    assert result["channel"] == "wecom"
    assert result["prompt"] == "请回复"
    assert result["instance_key"] == "card-1"


# ---------- _execute_definition 挂起行为 ----------


@pytest.mark.asyncio
async def test_execute_definition_suspends_on_approval():
    """approval 节点执行后 run 进入 suspended 且 signal 写入 waiting_for。"""
    definition = {
        "nodes": [
            {"id": "n1", "type": "value", "config": {"value": "start"}},
            {"id": "approve", "type": "approval", "config": {"channel": "feishu", "approval_code": "RECxyz"}},
        ],
        "edges": [{"from": "n1", "to": "approve"}],
    }
    run = SimpleNamespace(
        status=ExecutionStatus.running,
        node_states={service.TRACE_KEY: []},
    )
    db = DummyDB()

    output, trace = await service._execute_definition(
        db=db, run=run, definition=definition, input_payload={}
    )

    assert run.status == ExecutionStatus.suspended
    assert output is None
    # 验证 waiting_for 已写入
    wf = service.get_waiting_for(run)
    assert wf is not None
    assert wf["type"] == "approval"
    assert wf["instance_key"] == "RECxyz"
    assert wf["node_id"] == "approve"
    # trace 含两条：n1 success + approve suspended
    assert len(trace) == 2
    assert trace[0]["status"] == "success"
    assert trace[1]["status"] == "suspended"
    # DB 已 flush
    assert db.flush_count >= 1


@pytest.mark.asyncio
async def test_execute_definition_suspends_mid_dag():
    """DAG 中间节点挂起时，前面节点的 outputs 被持久化，后续节点不执行。"""
    definition = {
        "nodes": [
            {"id": "n1", "type": "value", "config": {"value": "first"}},
            {"id": "ask", "type": "human_input", "config": {"channel": "feishu", "prompt": "输入"}},
            {"id": "n3", "type": "value", "config": {"value": "should_not_run"}},
        ],
        "edges": [
            {"from": "n1", "to": "ask"},
            {"from": "ask", "to": "n3"},
        ],
    }
    run = SimpleNamespace(
        status=ExecutionStatus.running,
        node_states={service.TRACE_KEY: []},
    )
    db = DummyDB()

    output, trace = await service._execute_definition(
        db=db, run=run, definition=definition, input_payload={}
    )

    assert run.status == ExecutionStatus.suspended
    # n3 未执行（trace 只有 n1 + ask）
    assert len(trace) == 2
    assert trace[1]["status"] == "suspended"
    # outputs 已持久化到 node_states
    cached = run.node_states.get(service.OUTPUTS_CACHE_KEY, {})
    assert "n1" in cached
    assert cached["n1"] == "first"
    # ask 还没产出（等 resume）
    assert "ask" not in cached
    # n3 不在 trace 中
    node_ids_in_trace = [t["node_id"] for t in trace]
    assert "n3" not in node_ids_in_trace


@pytest.mark.asyncio
async def test_execute_definition_suspend_then_cancel_is_cancel():
    """cancel_requested 在挂起节点之前被检测到 → cancelled 而非 suspended。"""
    definition = {
        "nodes": [
            {"id": "n1", "type": "value", "config": {"value": "ok"}},
            {"id": "approve", "type": "approval", "config": {"channel": "feishu", "approval_code": "REC"}},
        ],
        "edges": [{"from": "n1", "to": "approve"}],
    }
    run = SimpleNamespace(
        status=ExecutionStatus.running,
        node_states={service.TRACE_KEY: [], service.CANCEL_KEY: True},
    )
    db = DummyDB()

    output, trace = await service._execute_definition(
        db=db, run=run, definition=definition, input_payload={}
    )

    # cancel 优先于 suspend
    assert output is None  # n1 不在 outputs（被 break 中断，没走到最后）
    assert trace[0]["status"] == "cancelled"
    assert trace[0]["reason"] == "cancel_requested"


@pytest.mark.asyncio
async def test_execute_definition_keeps_trace_intact_on_suspend():
    """挂起时 trace 中保留已完成节点的记录。"""
    definition = {
        "nodes": [
            {"id": "v1", "type": "value", "config": {"value": "a"}},
            {"id": "v2", "type": "value", "config": {"value": "b"}},
            {"id": "ask", "type": "human_input", "config": {"prompt": "?"}},
        ],
        "edges": [
            {"from": "v1", "to": "v2"},
            {"from": "v2", "to": "ask"},
        ],
    }
    run = SimpleNamespace(
        status=ExecutionStatus.running,
        node_states={service.TRACE_KEY: []},
    )
    db = DummyDB()

    _, trace = await service._execute_definition(
        db=db, run=run, definition=definition, input_payload={}
    )

    assert len(trace) == 3
    assert trace[0] == {"node_id": "v1", "node_type": "value", "status": "success", "attempt": 1, "output": "a"}
    assert trace[1] == {"node_id": "v2", "node_type": "value", "status": "success", "attempt": 1, "output": "b"}
    assert trace[2]["status"] == "suspended"
    assert trace[2]["node_id"] == "ask"


# ---------- execute_run 对 suspended 状态的正确流转 ----------


def _make_minimal_definition():
    return {
        "nodes": [
            {"id": "n1", "type": "value", "config": {"value": "ok"}},
            {"id": "approve", "type": "approval", "config": {"channel": "feishu", "approval_code": "REC"}},
        ],
        "edges": [{"from": "n1", "to": "approve"}],
    }


class FakeWorkflow:
    definition = _make_minimal_definition()


@pytest.mark.asyncio
async def test_execute_run_sets_suspended_without_completed_at():
    """execute_run 遇到 approve 节点挂起后，completed_at 为 None。"""
    from openagentic.workflow.models import WorkflowExecution

    run = WorkflowExecution(
        status=ExecutionStatus.pending,
        node_states={service.TRACE_KEY: []},
        input_data={},
    )
    # 不需要真正 commit，只需要 flush 被 DummyDB 拦截即可
    db = DummyDB()

    result = await service.execute_run(db, run, FakeWorkflow())

    assert result.status == ExecutionStatus.suspended
    assert result.completed_at is None
    # node_states 保留了 outputs 缓存
    assert service.OUTPUTS_CACHE_KEY in (result.node_states or {})


@pytest.mark.asyncio
async def test_execute_run_does_not_overwrite_suspended_node_states():
    """execute_run 在 suspended 路径不覆盖 _execute_definition 写入的 outputs 缓存。"""
    from openagentic.workflow.models import WorkflowExecution

    run = WorkflowExecution(
        status=ExecutionStatus.pending,
        node_states={service.TRACE_KEY: []},
        input_data={},
    )
    db = DummyDB()

    result = await service.execute_run(db, run, FakeWorkflow())

    assert result.status == ExecutionStatus.suspended
    # outputs 缓存未被 execute_run 的后续逻辑清除
    assert service.OUTPUTS_CACHE_KEY in (result.node_states or {})
    cached = result.node_states[service.OUTPUTS_CACHE_KEY]
    assert "n1" in cached
    assert cached["n1"] == "ok"


@pytest.mark.asyncio
async def test_execute_run_suspended_not_in_terminal():
    """suspended 不在终态集合中。"""
    assert ExecutionStatus.suspended not in TERMINAL_STATUSES
    # 验证 execute_run 的 finally 块不会对 suspended 设 completed_at
    from openagentic.workflow.models import WorkflowExecution

    run = WorkflowExecution(
        status=ExecutionStatus.pending,
        node_states={service.TRACE_KEY: []},
        input_data={},
    )
    db = DummyDB()

    result = await service.execute_run(db, run, FakeWorkflow())
    assert result.completed_at is None


# ---------- _execute_node 不支持的类型仍然抛错 ----------


@pytest.mark.asyncio
async def test_execute_node_unknown_type_raises():
    with pytest.raises(ValueError, match="Unsupported node type"):
        await service._execute_node("imaginary_type", {})
