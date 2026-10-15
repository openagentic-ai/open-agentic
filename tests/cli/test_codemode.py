import asyncio

import pytest


@pytest.mark.asyncio
async def test_codemode_parallel_calls_return_only_selected_fields():
    from openagentic.runtime.codemode import run_script
    active = 0
    peak = 0
    async def tool(name, args):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(0.02)
        active -= 1
        return {"id": args["id"], "large_secret_field": "hidden"}
    result = await run_script('const results = await Promise.all([tools.lookup({id: 1}), tools.lookup({id: 2})]); return results.map(x => x.id);', tool, tool_names=["lookup"], read_only_tools={"lookup"})
    assert result == "[1, 2]"
    assert peak == 2
    assert "hidden" not in result


@pytest.mark.asyncio
async def test_codemode_has_no_host_access_and_enforces_limits():
    from openagentic.runtime.codemode import run_script
    async def tool(*args):
        raise AssertionError("no tool should execute")
    result = await run_script('return [typeof process, typeof require, typeof fetch];', tool)
    assert result == '["undefined", "undefined", "undefined"]'
    assert "ERROR" in await run_script('while(true) {}', tool, timeout=0.2)
    assert "ERROR" in await run_script('return "x".repeat(1000);', tool, max_output=50)
    assert "ERROR" in await run_script('return await tools.codemode({code:""});', tool, tool_names=["codemode"])


@pytest.mark.asyncio
async def test_codemode_preserves_tool_denial(tmp_path, monkeypatch):
    from openagentic.runtime.agent import AgentSession
    from openagentic.cli import permissions
    monkeypatch.setattr(permissions, "decide", lambda *args: (permissions.DECISION_DENY, "blocked"))
    session = AgentSession(model="test", session_dir=tmp_path / "sessions", codemode=True)
    target = tmp_path / "file.txt"
    try:
        result = await session.execute_tool("codemode", {"code": 'return await tools.write_file(' +
            __import__("json").dumps({"path": str(target), "content": "oops"}) + ');'})
        assert "REFUSED" in result
        assert not target.exists()
    finally:
        await session.close()
