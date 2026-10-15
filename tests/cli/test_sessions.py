"""Durable CLI history, branch isolation and tool boundaries."""

import pytest


def make_store(tmp_path, cwd="project"):
    from openagentic.cli.sessions import SessionStore
    return SessionStore(tmp_path / "sessions", tmp_path / cwd)


def test_restart_restores_history_and_keeps_other_workspaces_separate(tmp_path):
    store = make_store(tmp_path)
    sid = store.create()
    messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "goal"}]
    store.save(messages)
    store.close()
    restored = make_store(tmp_path)
    assert restored.resume(sid) == messages
    assert restored.resume() == messages
    other = make_store(tmp_path, "other")
    assert other.list_sessions() == []
    with pytest.raises(ValueError):
        other.resume(sid)


def test_checkout_creates_branch_and_retains_original(tmp_path):
    store = make_store(tmp_path)
    store.create()
    root = [{"role": "system", "content": "rules"}, {"role": "user", "content": "goal"}]
    store.save(root)
    branch_point = store.head
    store.save([*root, {"role": "assistant", "content": "approach A"}])
    old_head = store.head
    assert store.checkout(branch_point) == root
    store.save([*root, {"role": "user", "content": "try B"}])
    assert store.checkout(old_head)[-1]["content"] == "approach A"
    assert {n["id"] for n in store.tree()} >= {branch_point, old_head}


def test_compaction_keeps_original_branch_and_restores_summary(tmp_path):
    store = make_store(tmp_path)
    store.create()
    original = [{"role": "system", "content": "rules"}, {"role": "user", "content": "EARLY_GOAL"}]
    store.save(original)
    original_head = store.head
    compacted = [{"role": "system", "content": "rules\n\n[Conversation Summary]\nsummary"}]
    store.save(compacted)
    assert store.resume(store.id) == compacted
    assert store.checkout(original_head) == original


def test_rejects_cross_session_node_and_incomplete_tool_boundary(tmp_path):
    store = make_store(tmp_path)
    store.create()
    messages = [{"role": "assistant", "tool_calls": [{"id": "t1"}, {"id": "t2"}]}]
    store.save(messages)
    incomplete = store.head
    with pytest.raises(ValueError, match="tool"):
        store.checkout(incomplete)
    store.save([*messages, {"role": "tool", "tool_call_id": "t1", "content": "ok"},
                {"role": "tool", "tool_call_id": "t2", "content": "ok"}])
    assert store.checkout(store.head)[-1]["tool_call_id"] == "t2"
    store.create()
    with pytest.raises(ValueError):
        store.checkout(incomplete)


def test_two_processes_cannot_silently_overwrite_same_session(tmp_path):
    store = make_store(tmp_path)
    sid = store.create()
    store.save([{"role": "user", "content": "first"}])
    other = make_store(tmp_path)
    other.resume(sid)
    store.save([{"role": "user", "content": "first"}, {"role": "assistant", "content": "second"}])
    with pytest.raises(ValueError, match="changed"):
        other.save([{"role": "user", "content": "stale"}])


def test_fork_does_not_change_source_session_head(tmp_path):
    store = make_store(tmp_path)
    source = store.create()
    root = [{"role": "system", "content": "rules"}, {"role": "user", "content": "goal"}]
    store.save(root)
    node = store.head
    store.save([*root, {"role": "assistant", "content": "A"}])
    assert store.fork(node) == root
    assert store.id != source
    store.save([*root, {"role": "assistant", "content": "B"}])
    assert store.resume(source)[-1]["content"] == "A"


def test_session_commands_restore_and_branch(tmp_path):
    from openagentic.cli.session_commands import handle_session_command
    store = make_store(tmp_path)
    sid = store.create()
    root = [{"role": "system", "content": "rules"}, {"role": "user", "content": "goal"}]
    store.save(root)
    node = store.head
    messages = [*root, {"role": "assistant", "content": "A"}]
    store.save(messages)
    assert handle_session_command(f"/tree {node}", store, messages, lambda: None)
    assert messages == root
    assert handle_session_command("/fork", store, messages, lambda: None)
    assert store.id != sid
    assert handle_session_command(f"/resume {sid}", store, messages, lambda: None)
    assert store.id == sid
    assert messages == root
    assert not handle_session_command("hello", store, messages, lambda: None)


@pytest.mark.asyncio
async def test_steering_waits_for_complete_tool_batch(monkeypatch):
    from openagentic.cli import react
    from openagentic.cli.turn_control import TurnControl, turn_control
    from unittest.mock import AsyncMock
    control = TurnControl()
    messages = [{"role": "system", "content": "rules"}]
    seen = []
    async def chat(history, *args, **kwargs):
        seen.append([dict(m) for m in history])
        if len(seen) == 1:
            return {"message": {"role": "assistant", "tool_calls": [
                {"id": "t1", "function": {"name": "read_file", "arguments": {}}},
                {"id": "t2", "function": {"name": "read_file", "arguments": {}}},
            ]}}
        return {"message": {"role": "assistant", "content": "adjusted"}}
    async def execute(*args, **kwargs):
        control.steering.append("change direction")
        return "ok"
    monkeypatch.setattr(react, "litellm_chat", chat)
    monkeypatch.setattr(react, "execute_tool", execute)
    monkeypatch.setattr(react, "prepare_context", AsyncMock(return_value=""))
    monkeypatch.setattr(react, "working_memory_compressible", lambda m: False)
    token = turn_control.set(control)
    try:
        assert await react.react_loop("goal", messages, "test", None, None) == "adjusted"
    finally:
        turn_control.reset(token)
    roles = [m["role"] for m in seen[1]]
    assert roles == ["system", "user", "assistant", "tool", "tool", "user", "user"]
    assert seen[1][-1]["content"] == "change direction"


@pytest.mark.asyncio
async def test_steering_received_during_final_response_continues(monkeypatch):
    from openagentic.cli import react
    from openagentic.cli.turn_control import TurnControl, turn_control
    from unittest.mock import AsyncMock
    control = TurnControl()
    calls = []
    async def chat(history, *args, **kwargs):
        calls.append([dict(m) for m in history])
        if len(calls) == 1:
            control.steering.append("use B")
        return {"message": {"role": "assistant", "content": "answer"}}
    monkeypatch.setattr(react, "litellm_chat", chat)
    monkeypatch.setattr(react, "prepare_context", AsyncMock(return_value=""))
    monkeypatch.setattr(react, "working_memory_compressible", lambda m: False)
    token = turn_control.set(control)
    try:
        await react.react_loop("goal", [{"role": "system", "content": "rules"}], "test", None, None)
    finally:
        turn_control.reset(token)
    assert len(calls) == 2
    assert calls[1][-1] == {"role": "user", "content": "use B"}
