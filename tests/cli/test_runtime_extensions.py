"""Executable extensions use the same tool gate as ordinary agent calls."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_extension_blocks_builtin_tool_before_side_effect(tmp_path, monkeypatch):
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions

    ext = Extensions()
    async def guard(call):
        if call["arguments"].get("path", "").endswith("migration.sql"):
            return {**call, "blocked": "protected migration"}
    ext.on("tool_call", guard)
    target = tmp_path / "migration.sql"
    session = AgentSession(model="test", extensions=ext, session_dir=tmp_path / "sessions")
    try:
        result = await session.execute_tool("write_file", {"path": str(target), "content": "oops"})
        assert "protected migration" in result
        assert not target.exists()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_extension_custom_tool_requires_confirmation_and_transforms_result(tmp_path):
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions

    ext = Extensions()
    executed = []
    async def echo(args):
        executed.append(args["value"])
        return "raw result"
    ext.register_tool("echo", "Echo a value", {"type": "object", "properties": {
        "value": {"type": "string"}}, "required": ["value"]}, echo)
    async def redact(result):
        return {**result, "result": "redacted"}
    ext.on("tool_result", redact)
    session = AgentSession(model="test", extensions=ext, session_dir=tmp_path / "sessions")
    try:
        assert "REFUSED" in await session.execute_tool("echo", {"value": "secret"})
        assert executed == []
        session.confirm_fn = AsyncMock(return_value=True)
        assert await session.execute_tool("echo", {"value": "secret"}) == "redacted"
        assert executed == ["secret"]
        assert "ERROR" in await session.execute_tool("echo", {"value": 12})
        assert executed == ["secret"]
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_extension_provider_context_events_commands_and_cleanup(tmp_path):
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions

    ext = Extensions()
    seen = []
    async def context(messages):
        return [*messages, {"role": "user", "content": "extra context"}]
    async def complete(messages, *args, **kwargs):
        assert messages[-1]["content"] == "extra context"
        return {"message": {"role": "assistant", "content": "CUSTOM_PROVIDER_OK"}}
    async def shutdown(event):
        seen.append(event["session_id"])
    ext.register_provider("fake", complete)
    ext.on("context", context)
    ext.on("session_shutdown", shutdown)
    ext.register_command("hello", AsyncMock(return_value="hello world"))
    ext.register_status("test", lambda: "active")
    session = AgentSession(model="fake/test", extensions=ext, session_dir=tmp_path / "sessions")
    try:
        assert await session.prompt("goal") == "CUSTOM_PROVIDER_OK"
        assert await session.command("hello", "") == "hello world"
        assert ext.status() == "active"
        assert not any(m.get("content") == "extra context" for m in session.messages)
        sid = session.id
    finally:
        await session.close()
    assert seen == [sid]


def test_only_explicit_extension_file_is_loaded(tmp_path):
    from openagentic.runtime.extensions import Extensions
    path = tmp_path / "custom.py"
    path.write_text('def setup(api):\n    api.register_status("custom", lambda: "loaded")\n')
    ext = Extensions()
    assert ext.status() == ""
    ext.load([path])
    assert ext.status() == "loaded"


def test_extension_command_is_discoverable_in_cli():
    from prompt_toolkit.document import Document
    from openagentic.cli.slash_commands import SlashCompleter
    completer = SlashCompleter(["/hello"])
    assert "/hello" in [item.text for item in completer.get_completions(Document("/he"), None)]


@pytest.mark.asyncio
async def test_sdk_busy_steering_and_persistent_resume(tmp_path):
    import asyncio
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions

    ext = Extensions()
    started, release = asyncio.Event(), asyncio.Event()
    seen = []
    async def complete(messages, *args, **kwargs):
        seen.append([dict(m) for m in messages])
        if len(seen) == 1:
            started.set()
            await release.wait()
        return {"message": {"role": "assistant", "content": "OK"}}
    ext.register_provider("fake", complete)
    session = AgentSession(model="fake/test", extensions=ext, session_dir=tmp_path / "sessions")
    try:
        task = asyncio.create_task(session.prompt("first"))
        await started.wait()
        session.steer("adjust")
        session.follow_up("later")
        with pytest.raises(RuntimeError, match="busy"):
            await session.prompt("concurrent")
        release.set()
        assert await task == "OK"
        assert seen[1][-1]["content"] == "adjust"
        assert seen[2][-1]["content"] == "later"
        sid = session.id
    finally:
        await session.close()
    resumed = AgentSession(model="fake/test", session_dir=tmp_path / "sessions", resume=sid)
    try:
        assert any(m.get("content") == "later" for m in resumed.messages)
    finally:
        await resumed.close()


@pytest.mark.asyncio
async def test_cancelled_tool_is_not_reexecuted_on_resume(tmp_path):
    import asyncio
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions
    from openagentic.cli.turn_control import pending_tool_calls

    ext = Extensions()
    entered = asyncio.Event()
    executions = []
    async def slow(args):
        executions.append(1)
        entered.set()
        await asyncio.sleep(60)
        return "unreachable"
    async def complete(*args, **kwargs):
        return {"message": {"role": "assistant", "tool_calls": [{"id": "slow1",
            "function": {"name": "slow_tool", "arguments": {}}}]}}
    ext.register_tool("slow_tool", "slow", {"type": "object"}, slow)
    ext.register_provider("fake", complete)
    session = AgentSession(model="fake/test", extensions=ext,
        confirm_fn=AsyncMock(return_value=True), session_dir=tmp_path / "sessions")
    task = asyncio.create_task(session.prompt("start"))
    await asyncio.wait_for(entered.wait(), 5)
    sid = session.id
    session.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not pending_tool_calls(session.messages)
    assert "INTERRUPTED" in session.messages[-1]["content"]
    await session.close()
    resumed = AgentSession(model="fake/test", session_dir=tmp_path / "sessions", resume=sid)
    try:
        assert not pending_tool_calls(resumed.messages)
        assert executions == [1]
    finally:
        await resumed.close()
