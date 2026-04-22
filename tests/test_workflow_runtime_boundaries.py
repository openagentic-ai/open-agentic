"""Boundary tests for async workflow execution behavior."""

import asyncio
from types import SimpleNamespace

import pytest

from openagentic.workflow import service


class DummyDB:
    async def refresh(self, _run):
        return None


@pytest.mark.asyncio
async def test_execute_definition_retries_then_succeeds(monkeypatch):
    definition = {
        "nodes": [{"id": "tool1", "type": "tool", "config": {"tool_name": "echo", "arg": "x", "retries": 1}}],
        "edges": [],
    }
    run = SimpleNamespace(cancel_requested=False)
    db = DummyDB()
    calls = {"n": 0}

    async def flaky_execute_node(node_type, config):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("temporary failure")
        return "ok-after-retry"

    monkeypatch.setattr(service, "_execute_node", flaky_execute_node)
    output, trace = await service._execute_definition(  # noqa: SLF001
        db=db, run=run, definition=definition, input_payload={}
    )
    assert output == "ok-after-retry"
    assert any(item["status"] == "retrying" for item in trace)
    assert any(item["status"] == "success" and item["attempt"] == 2 for item in trace)


@pytest.mark.asyncio
async def test_execute_definition_timeout_marks_failed(monkeypatch):
    definition = {
        "nodes": [{"id": "slow", "type": "value", "config": {"value": "x", "timeout_sec": 0.01}}],
        "edges": [],
    }
    run = SimpleNamespace(cancel_requested=False)
    db = DummyDB()

    async def slow_execute_node(node_type, config):
        await asyncio.sleep(0.05)
        return "too-late"

    monkeypatch.setattr(service, "_execute_node", slow_execute_node)
    with pytest.raises(RuntimeError, match="Node slow failed"):
        await service._execute_definition(  # noqa: SLF001
            db=db, run=run, definition=definition, input_payload={}
        )


@pytest.mark.asyncio
async def test_execute_definition_honors_cancel_requested():
    definition = {
        "nodes": [
            {"id": "n1", "type": "value", "config": {"value": "1"}},
            {"id": "n2", "type": "value", "config": {"value": "2"}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    run = SimpleNamespace(cancel_requested=True)
    db = DummyDB()
    output, trace = await service._execute_definition(  # noqa: SLF001
        db=db, run=run, definition=definition, input_payload={}
    )
    assert output is None
    assert trace
    assert trace[0]["status"] == "cancelled"

