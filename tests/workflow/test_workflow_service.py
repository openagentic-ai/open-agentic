"""Unit tests for Phase 3 workflow service helpers."""

from unittest.mock import AsyncMock

import pytest

from openagentic.workflow import service


def test_validate_definition_accepts_valid_dag():
    definition = {
        "nodes": [
            {"id": "input_node", "type": "value", "config": {"value": "hello"}},
            {"id": "tool_node", "type": "tool", "config": {"tool_name": "echo", "arg": "{{nodes.input_node}}"}},
        ],
        "edges": [{"from": "input_node", "to": "tool_node"}],
    }
    service.validate_definition(definition)


def test_validate_definition_rejects_cycle():
    definition = {
        "nodes": [
            {"id": "a", "type": "value", "config": {"value": "1"}},
            {"id": "b", "type": "value", "config": {"value": "2"}},
        ],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    with pytest.raises(ValueError, match="cycle"):
        service.validate_definition(definition)


def test_render_template_supports_input_and_node_refs():
    rendered = service._render_template(  # noqa: SLF001
        "user={{input.user}};answer={{nodes.calc}}",
        {"input": {"user": "allen"}, "nodes": {"calc": "42"}},
    )
    assert rendered == "user=allen;answer=42"


@pytest.mark.asyncio
async def test_execute_node_tool_and_value():
    value_output = await service._execute_node("value", {"value": "ok"})  # noqa: SLF001
    assert value_output == "ok"

    tool_output = await service._execute_node(  # noqa: SLF001
        "tool", {"tool_name": "echo", "arg": "ping"}
    )
    assert tool_output == "ping"


# ---------- feishu / wecom 节点 ----------


@pytest.mark.asyncio
async def test_execute_node_feishu_calls_run_cli(monkeypatch):
    """feishu 节点调用 lark-cli，返回 {stdout, stderr, returncode}。"""
    async def fake_run_cli(binary, subcommand, args):
        return {"stdout": "ok", "stderr": "", "returncode": 0}

    monkeypatch.setattr(service, "_run_cli", fake_run_cli)

    result = await service._execute_node(  # noqa: SLF001
        "feishu", {"subcommand": "im send", "args": ["--receive-id", "ou_123", "--content", "hello"]}
    )
    assert result["stdout"] == "ok"
    assert result["returncode"] == 0


@pytest.mark.asyncio
async def test_execute_node_wecom_calls_run_cli(monkeypatch):
    """wecom 节点调用 wecom-cli。"""
    async def fake_run_cli(binary, subcommand, args):
        assert binary == "wecom-cli"
        return {"stdout": "sent", "stderr": "", "returncode": 0}

    monkeypatch.setattr(service, "_run_cli", fake_run_cli)

    result = await service._execute_node(  # noqa: SLF001
        "wecom", {"subcommand": "im send", "args": ["--chat-id", "room_1", "--content", "test"]}
    )
    assert result["stdout"] == "sent"


@pytest.mark.asyncio
async def test_execute_node_feishu_requires_subcommand():
    """feishu 节点缺少 subcommand 抛错。"""
    with pytest.raises(ValueError, match="subcommand"):
        await service._execute_node("feishu", {})  # noqa: SLF001


@pytest.mark.asyncio
async def test_execute_node_wecom_requires_subcommand():
    """wecom 节点缺少 subcommand 抛错。"""
    with pytest.raises(ValueError, match="subcommand"):
        await service._execute_node("wecom", {})  # noqa: SLF001


def test_validate_definition_accepts_feishu_and_wecom():
    service.validate_definition({
        "nodes": [
            {"id": "start", "type": "value", "config": {"value": "go"}},
            {"id": "fs", "type": "feishu", "config": {"subcommand": "im send", "args": ["--content", "test"]}},
            {"id": "wc", "type": "wecom", "config": {"subcommand": "im send", "args": ["--content", "test"]}},
        ],
        "edges": [
            {"from": "start", "to": "fs"},
            {"from": "fs", "to": "wc"},
        ],
    })


# ---------- 条件边 (condition edge) — Phase 7 P0 ----------


def test_evaluate_condition_equals():
    ctx = {"nodes": {"approval": "approved"}}
    assert service._evaluate_condition(  # noqa: SLF001
        '{{nodes.approval}} == "approved"', ctx
    ) is True
    assert service._evaluate_condition(  # noqa: SLF001
        '{{nodes.approval}} == "rejected"', ctx
    ) is False


def test_evaluate_condition_not_equals():
    ctx = {"nodes": {"status": "pending"}}
    assert service._evaluate_condition(  # noqa: SLF001
        '{{nodes.status}} != "done"', ctx
    ) is True
    assert service._evaluate_condition(  # noqa: SLF001
        '{{nodes.status}} != "pending"', ctx
    ) is False


def test_evaluate_condition_truthy():
    ctx = {"nodes": {"result": "ok"}}
    assert service._evaluate_condition("{{nodes.result}}", ctx) is True  # noqa: SLF001
    # 空字符串为 falsy
    ctx2 = {"nodes": {"result": ""}}
    assert service._evaluate_condition("{{nodes.result}}", ctx2) is False  # noqa: SLF001


def test_evaluate_condition_nonexistent():
    ctx = {"nodes": {}}
    assert service._evaluate_condition(  # noqa: SLF001
        "{{nodes.missing}}", ctx
    ) is False


def test_should_skip_node_unconditional_edge():
    """无条件边的节点始终执行。"""
    definition = {
        "nodes": [{"id": "input", "type": "value"}, {"id": "step2", "type": "tool"}],
        "edges": [{"from": "input", "to": "step2"}],
    }
    skip, reason = service._should_skip_node("step2", definition, {})  # noqa: SLF001
    assert skip is False
    assert reason == ""


def test_should_skip_node_when_condition_false():
    """所有入边条件为 False 时跳过。"""
    definition = {
        "nodes": [{"id": "check", "type": "llm"}, {"id": "action", "type": "tool"}],
        "edges": [{"from": "check", "to": "action", "condition": '{{nodes.check}} == "yes"'}],
    }
    skip, reason = service._should_skip_node(  # noqa: SLF001
        "action", definition, {"check": "no"}
    )
    assert skip is True
    assert "check→action" in reason


def test_should_skip_node_when_condition_true():
    """条件为 True 时不跳过。"""
    definition = {
        "nodes": [{"id": "check", "type": "llm"}, {"id": "action", "type": "tool"}],
        "edges": [{"from": "check", "to": "action", "condition": '{{nodes.check}} == "yes"'}],
    }
    skip, _ = service._should_skip_node(  # noqa: SLF001
        "action", definition, {"check": "yes"}
    )
    assert skip is False


def test_should_skip_node_mixed_edges():
    """有至少一条无条件入边时，即使条件边为 False 也执行。"""
    definition = {
        "nodes": [
            {"id": "check", "type": "llm"},
            {"id": "fallback", "type": "value"},
            {"id": "action", "type": "tool"},
        ],
        "edges": [
            {"from": "check", "to": "action", "condition": '{{nodes.check}} == "yes"'},
            {"from": "fallback", "to": "action"},  # 无条件边
        ],
    }
    skip, _ = service._should_skip_node(  # noqa: SLF001
        "action", definition, {"check": "no"}
    )
    assert skip is False  # fallback 无条件边保证执行

