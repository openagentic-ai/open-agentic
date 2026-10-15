import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_spinner_uses_layout_and_clears_on_cancel(capsys):
    from openagentic.cli.status import ActivityStatus, activity_status
    from openagentic.cli.react import _spin_while

    status = ActivityStatus()
    token = activity_status.set(status)
    task = asyncio.create_task(_spin_while(asyncio.sleep(10), text="working"))
    try:
        await asyncio.sleep(0)
        assert status.text == "working"
        assert status.frame(0) != status.frame(1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert status.text == ""
        assert capsys.readouterr().out == ""
    finally:
        activity_status.reset(token)


@pytest.mark.asyncio
async def test_compaction_preserves_early_goals_and_tool_pairs(monkeypatch):
    from openagentic.memory.manager import compress_working_memory

    chat = AsyncMock(return_value={"message": {"content": "summary"}})
    monkeypatch.setattr("openagentic.cli.llm.litellm_chat", chat)
    messages = [{"role": "system", "content": "instructions"},
                {"role": "user", "content": "EARLY_GOAL" + "x" * 7000}]
    messages += [{"role": "assistant", "content": "step"}] * 8
    messages += [{"role": "assistant", "tool_calls": [{"id": "t1"}]},
                 {"role": "tool", "tool_call_id": "t1", "content": "result"},
                 {"role": "user", "content": "continue"}]
    result = await compress_working_memory(messages, keep_recent=2)
    assert "EARLY_GOAL" in chat.call_args.args[0][0]["content"]
    assert result[1]["role"] == "assistant"
    assert result[2]["tool_call_id"] == "t1"
    assert messages[0]["content"] == "instructions"


@pytest.mark.asyncio
async def test_failed_compaction_keeps_history(monkeypatch):
    from openagentic.memory.manager import compress_working_memory

    monkeypatch.setattr("openagentic.cli.llm.litellm_chat", AsyncMock(side_effect=RuntimeError("offline")))
    messages = [{"role": "system", "content": "instructions"}]
    messages += [{"role": "user", "content": str(i)} for i in range(15)]
    assert await compress_working_memory(messages) == messages


@pytest.mark.asyncio
async def test_repeated_compaction_carries_previous_summary(monkeypatch):
    from openagentic.memory.manager import compress_working_memory

    chat = AsyncMock(return_value={"message": {"content": "updated summary"}})
    monkeypatch.setattr("openagentic.cli.llm.litellm_chat", chat)
    messages = [{"role": "system", "content": "rules\n\n[Conversation Summary]\nEARLY_GOAL"}]
    messages += [{"role": "user", "content": str(i)} for i in range(15)]
    result = await compress_working_memory(messages)
    assert "EARLY_GOAL" in chat.call_args.args[0][0]["content"]
    assert result[0]["content"] == "rules\n\n[Conversation Summary]\nupdated summary"
    assert messages[0]["content"].endswith("EARLY_GOAL")


@pytest.mark.asyncio
async def test_empty_compaction_keeps_history(monkeypatch):
    from openagentic.memory.manager import compress_working_memory

    monkeypatch.setattr("openagentic.cli.llm.litellm_chat",
                        AsyncMock(return_value={"message": {"content": " "}}))
    messages = [{"role": "system", "content": "rules"}]
    messages += [{"role": "user", "content": str(i)} for i in range(15)]
    assert await compress_working_memory(messages) == messages


@pytest.mark.asyncio
async def test_precise_edit_requires_unique_match_and_write_permission(tmp_path, monkeypatch):
    from openagentic.cli.tools import execute_tool
    from openagentic.cli import permissions

    target = tmp_path / "example.py"
    target.write_text("value = 1\nvalue = 1\n")
    confirm = AsyncMock(return_value=True)
    def decide(name, args):
        return permissions.DECISION_ASK, ""
    monkeypatch.setattr(permissions, "decide", decide)
    args = {"path": str(target), "old_text": "value = 1", "new_text": "value = 2"}
    assert "ERROR" in await execute_tool("edit_file", args, confirm_fn=confirm)
    confirm.assert_not_awaited()
    target.write_text("value = 1\n")
    assert "OK" in await execute_tool("edit_file", args, confirm_fn=confirm)
    assert target.read_text() == "value = 2\n"
    assert "diff:" in confirm.call_args.args[1]
    seen = []
    def deny(name, args):
        seen.append(name)
        return permissions.DECISION_DENY, "blocked"
    monkeypatch.setattr(permissions, "decide", deny)
    assert "REFUSED" in await execute_tool("edit_file", args, confirm_fn=confirm)
    assert seen == ["write_file"]


@pytest.mark.asyncio
async def test_edit_does_not_overwrite_concurrent_changes(tmp_path, monkeypatch):
    from openagentic.cli.tools import execute_tool
    from openagentic.cli import permissions

    monkeypatch.setattr(permissions, "decide", lambda *args: (permissions.DECISION_ASK, ""))
    target = tmp_path / "example.py"
    target.write_text("value = 1\n")
    async def confirm(*args):
        target.write_text("external change\n")
        return True
    result = await execute_tool("edit_file", {
        "path": str(target), "old_text": "value = 1", "new_text": "value = 2",
    }, confirm_fn=confirm)
    assert "ERROR" in result
    assert target.read_text() == "external change\n"


@pytest.mark.parametrize("edit", [False, True])
def test_cli_real_terminal_turn_and_exit(tmp_path, edit):
    """Exercise the real prompt/producer/consumer layout in a pseudo-terminal."""
    import os
    import sys
    pexpect = pytest.importorskip("pexpect")
    script = '''
import asyncio
import json
import os
from unittest.mock import AsyncMock
import openagentic.cli.repl as repl
import openagentic.cli.react as react
from openagentic.skills import SkillsManager
from openagentic.cli import permissions
permissions.decide = lambda *args: (permissions.DECISION_ASK, "")
repl.detect_local_model = lambda: None
repl.require_provider_configured = lambda provider: ("http://localhost:1/v1", None)
repl.resolve_model_for_provider = lambda provider, model: model
repl._apply_automodel_defaults = lambda provider, model: model
SkillsManager.ensure_seeded = lambda self: []
react.prepare_context = AsyncMock(return_value="")
async def chat(*args, **kwargs):
    await asyncio.sleep(0.5)
    if os.environ.get("OPENAGENTIC_TEST_FILE") and not any(m.get("role") == "tool" for m in args[0]):
        return {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "id": "edit1", "type": "function", "function": {"name": "edit_file", "arguments": json.dumps({
                "path": os.environ["OPENAGENTIC_TEST_FILE"], "old_text": "value = 1", "new_text": "value = 2",
            })},
        }]}}
    return {"message": {"role": "assistant", "content": "REPLY_OK", "tool_calls": []}}
react.litellm_chat = chat
asyncio.run(repl.main_loop("local/test", "local"))
'''
    # CI shells often use TERM=dumb, which deliberately disables live rendering.
    target = tmp_path / "example.py"
    target.write_text("value = 1\n")
    child = pexpect.spawn(sys.executable, ["-c", script], encoding="utf-8", timeout=15,
                          env={**os.environ, "TERM": "xterm-256color",
                               "OPENAGENTIC_TEST_FILE": str(target) if edit else ""})
    try:
        child.expect("❯")
        child.sendline("hello")
        child.expect("思考中")
        if edit:
            child.expect("Confirm\\? ")
            child.sendline("y")
        child.expect("REPLY_OK")
        if edit:
            assert target.read_text() == "value = 2\n"
        child.sendline("/exit")
        child.expect("Bye!")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0
    finally:
        if child.isalive():
            child.terminate(force=True)
