import asyncio
import json
import os
import sys

import pytest


@pytest.mark.asyncio
async def test_rpc_cancel_immediately_after_queued_prompt(tmp_path):
    from openagentic.runtime.agent import AgentSession
    from openagentic.runtime.extensions import Extensions
    from openagentic.runtime.rpc import serve
    ext = Extensions()
    async def complete(*args, **kwargs):
        await asyncio.sleep(60)
    ext.register_provider("fake", complete)
    session = AgentSession(model="fake/test", extensions=ext, session_dir=tmp_path / "sessions")
    queue = asyncio.Queue()
    for value in [{"id": 1, "method": "prompt", "params": {"text": "work"}},
                  {"id": 2, "method": "cancel"}, {"id": 3, "method": "close"}]:
        queue.put_nowait(json.dumps(value))
    outputs = []
    await asyncio.wait_for(serve(session, queue, outputs.append), 5)
    prompt_response = next(v for v in outputs if v.get("id") == 1)
    assert prompt_response["error"]["code"] == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["runtime", "cli"])
async def test_rpc_subprocess_prompt_steer_followup_cancel_and_resume(tmp_path, entrypoint):
    extension = tmp_path / "fake.py"
    extension.write_text('''
import asyncio
def setup(api):
    print("extension diagnostic on stderr")
    async def complete(messages, *args, **kwargs):
        last = messages[-1].get("content")
        if last == "slow":
            await asyncio.sleep(2)
        elif last == "cancel_me":
            await asyncio.sleep(60)
        return {"message": {"role": "assistant", "content": "reply:" + str(last)}}
    api.register_provider("fake", complete)
''')
    async def spawn(resume=None):
        args = [sys.executable, "-m", "openagentic.runtime.rpc" if entrypoint == "runtime" else "openagentic.cli",
                "--model", "fake/test", "--extension", str(extension)]
        if entrypoint == "cli":
            args += ["--mode", "rpc"]
        if resume:
            args += ["--resume", resume]
        return await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": "src", "OPENAGENTIC_CLI_SESSION_DIR": str(tmp_path / "sessions"),
                 "OPENAGENTIC_API_BASE": "", "OPENAGENTIC_BASE_URL": "", "OPENAGENTIC_AUTH_TOKEN": "", "OPENAGENTIC_MODEL": ""})
    async def send(proc, rid, method, **params):
        proc.stdin.write((json.dumps({"id": rid, "method": method, "params": params}) + "\n").encode())
        await proc.stdin.drain()
    async def response(proc, rid):
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), 15)
            assert line, "RPC process exited without a response"
            value = json.loads(line)
            if value.get("id") == rid:
                return value
    proc = await spawn()
    try:
        await send(proc, 1, "state")
        state = (await response(proc, 1))["result"]
        sid = state["session_id"]
        # Malformed frames must yield an error and leave the next request usable.
        proc.stdin.write(b'not-json\n')
        await proc.stdin.drain()
        assert "error" in await response(proc, None)
        await send(proc, 2, "prompt", text="slow")
        # agent_start proves prompt execution has begun before steering it.
        while True:
            event = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
            if event.get("event", {}).get("type") == "agent_start":
                break
        await send(proc, 3, "steer", text="changed")
        assert "result" in await response(proc, 3)
        await send(proc, 4, "follow_up", text="later")
        assert "result" in await response(proc, 4)
        assert (await response(proc, 2))["result"] == "reply:later"
        await send(proc, 5, "prompt", text="cancel_me")
        while True:
            event = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
            if event.get("event", {}).get("type") == "agent_start":
                break
        await send(proc, 6, "cancel")
        # Both cancellation ack and the cancelled prompt response must arrive.
        received = {}
        while not {5, 6} <= received.keys():
            value = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
            if value.get("id") in {5, 6}:
                received[value["id"]] = value
        assert received[5]["error"]["code"] == "cancelled"
        await send(proc, 7, "close")
        assert "result" in await response(proc, 7)
        assert await asyncio.wait_for(proc.wait(), 10) == 0
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
    proc = await spawn(sid)
    try:
        await send(proc, 8, "state")
        history = (await response(proc, 8))["result"]["messages"]
        assert any(m.get("content") == "changed" for m in history)
        assert any(m.get("content") == "reply:later" for m in history)
        await send(proc, 9, "close")
        await response(proc, 9)
        assert await asyncio.wait_for(proc.wait(), 10) == 0
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
