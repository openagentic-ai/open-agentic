"""Real terminal test of steering, follow-ups and process restart."""

import json
import os
import sys

import pytest


def test_terminal_steering_followup_and_resume(tmp_path):
    pexpect = pytest.importorskip("pexpect")
    script = '''
import asyncio, json, os
from pathlib import Path
from unittest.mock import AsyncMock
import openagentic.cli.repl as repl
import openagentic.cli.react as react
from openagentic.skills import SkillsManager
repl.detect_local_model = lambda: None
repl.require_provider_configured = lambda p: ("http://localhost:1/v1", None)
repl.resolve_model_for_provider = lambda p, m: m
repl._apply_automodel_defaults = lambda p, m: m
SkillsManager.ensure_seeded = lambda self: []
react.prepare_context = AsyncMock(return_value="")
react.working_memory_compressible = lambda m: False
async def tool(*args, **kwargs):
    await asyncio.sleep(1.5)
    return "TOOL_OK"
react.execute_tool = tool
async def chat(messages, *args, **kwargs):
    with Path(os.environ["CALLS"]).open("a") as f:
        f.write(json.dumps(messages) + "\\n")
    last = messages[-1].get("content")
    if last == "goal":
        return {"message": {"role": "assistant", "tool_calls": [{"id": "t1", "function": {"name": "read_file", "arguments": {}}}]}}
    return {"message": {"role": "assistant", "content": "ANSWER_" + str(last)}}
react.litellm_chat = chat
asyncio.run(repl.main_loop("local/test", "local", resume_session=os.environ.get("RESUME")))
'''
    env = {**os.environ, "TERM": "xterm-256color", "PROMPT_TOOLKIT_NO_CPR": "1", "CALLS": str(tmp_path / "calls.jsonl"),
           "OPENAGENTIC_CLI_SESSION_DIR": str(tmp_path / "sessions")}
    child = pexpect.spawn(sys.executable, ["-c", script], encoding="utf-8", timeout=20, env=env)
    log = (tmp_path / "terminal.log").open("w")
    child.logfile_read = log
    try:
        child.expect("❯")
        child.sendline("goal")
        child.expect("✦ read_file")
        child.sendline("change_B")
        child.expect("已收到纠偏")
        child.send("later_task\x1b\r")
        child.expect("ANSWER_change_B")
        child.expect("ANSWER_later_task")
        child.sendline("/exit")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0
    finally:
        if child.isalive():
            child.terminate(force=True)
        log.close()
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert calls[1][-2]["role"] == "tool"
    assert calls[1][-1]["content"] == "change_B"
    assert calls[2][-2]["content"] == "ANSWER_change_B"
    assert calls[2][-1]["content"] == "later_task"
    env["RESUME"] = "latest"
    child = pexpect.spawn(sys.executable, ["-c", script], encoding="utf-8", timeout=20, env=env)
    try:
        child.expect("❯")
        child.sendline("check_history")
        child.expect("ANSWER_check_history")
        from openagentic.cli.sessions import SessionStore
        view = SessionStore(tmp_path / "sessions")
        view.resume()
        node = next(row["id"] for row in view.tree() if row["preview"] == "goal")
        view.close()
        child.sendline(f"/tree {node}")
        child.expect("已切换到节点")
        child.sendline("branch_B")
        child.expect("ANSWER_branch_B")
        child.sendline("/exit")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0
    finally:
        if child.isalive():
            child.terminate(force=True)
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert any(m.get("content") == "ANSWER_later_task" for m in calls[-2])
    assert not any(m.get("content") == "ANSWER_later_task" for m in calls[-1])
    view = SessionStore(tmp_path / "sessions")
    view.resume()
    assert any(row["preview"] == "ANSWER_later_task" for row in view.tree())
    view.close()
