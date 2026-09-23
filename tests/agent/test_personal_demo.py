"""个人简报边界：模型选择、无静默外发、来源与重启后持久化。"""
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from extensions.personal_demo.app import ModelSettings, create_app
from openagentic.agent.llm import litellm_chat


def local():
    return ModelSettings(model="openai/test", api_base="http://127.0.0.1:11434/v1")


@pytest.mark.parametrize("endpoint", ["https://example.com/v1", "http://localhost.evil/v1", "http://192.168.1.2/v1"])
def test_local_mode_rejects_non_loopback(endpoint):
    with pytest.raises(ValueError):
        ModelSettings(model="openai/test", api_base=endpoint).check()


async def test_explicit_no_escalation_blocks_cloud_even_when_configured(monkeypatch):
    fail = AsyncMock(side_effect=RuntimeError("local unavailable"))
    cloud = AsyncMock()
    monkeypatch.setattr("litellm.acompletion", fail)
    monkeypatch.setattr("openagentic.agent.llm._escalate_if_configured", cloud)
    with pytest.raises(RuntimeError, match="local unavailable"):
        await litellm_chat([], "openai/test", "http://127.0.0.1:11434/v1", "local",
                           allow_escalation=False)
    cloud.assert_not_called()


async def test_report_uses_tools_preferences_and_survives_restart(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "todo.md").write_text("周五归还相机")
    (notes / "outside.md").symlink_to(tmp_path / "secret")
    (tmp_path / "secret").write_text("private")
    state = tmp_path / "state"
    seen = []

    async def inference(**kwargs):
        seen.append(kwargs)
        messages = kwargs["messages"]
        count = sum(m["role"] == "tool" for m in messages)
        calls = [("list_notes", "{}"), ("read_note", '{"filename":"../secret"}'),
                 ("read_note", '{"filename":"todo.md"}')]
        if count < 3:
            name, arguments = calls[count]
            return {"message": {"content": "", "tool_calls": [{"id": str(count),
                    "type": "function", "function": {"name": name, "arguments": arguments}}]}}
        assert "private" not in str(messages)
        assert "只能读取" in str(messages)
        assert "周五归还相机" in str(messages)
        assert "简短中文" in messages[0]["content"]
        return {"message": {"content": "- 周五归还相机 [todo.md]"}}

    monkeypatch.setattr("openagentic.agent.engine.litellm_chat", inference)
    async with AsyncClient(transport=ASGITransport(app=create_app(notes, state, local())),
                           base_url="http://testserver") as client:
        assert (await client.post("/api/preferences", json={"text": "简短中文"})).status_code == 200
        response = await client.post("/api/run", json={})
        assert response.status_code == 200, response.text
        assert response.json()["sources"] == ["todo.md"]
    assert all(c["allow_escalation"] is False for c in seen)
    async with AsyncClient(transport=ASGITransport(app=create_app(notes, state, local())),
                           base_url="http://testserver") as client:
        restored = (await client.get("/api/state")).json()
        assert restored["preferences"] == "简短中文"
        assert "归还相机" in restored["report"]["content"]
        assert restored["notes"] == ["todo.md"]


async def test_api_key_is_usable_but_not_exposed_or_persisted(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "todo.md").write_text("归还相机")
    state = tmp_path / "state"
    calls = []

    async def inference(**kwargs):
        calls.append(kwargs)
        if not any(m["role"] == "tool" for m in kwargs["messages"]):
            return {"message": {"tool_calls": [{"id": "1", "type": "function",
                    "function": {"name": "read_note", "arguments": '{"filename":"todo.md"}'}}]}}
        return {"message": {"content": "归还相机 [todo.md]"}}

    monkeypatch.setattr("openagentic.agent.engine.litellm_chat", inference)
    async with AsyncClient(transport=ASGITransport(app=create_app(notes, state, local())),
                           base_url="http://testserver") as client:
        config = {"mode": "api", "model": "openai/example", "api_base": "https://example.com/v1",
                  "api_key": "test-secret-key"}
        assert (await client.post("/api/model", json=config)).status_code == 200
        assert (await client.post("/api/run", json={})).status_code == 200
        assert "test-secret-key" not in (await client.get("/api/state")).text
        assert (await client.post("/api/preferences", json={"text": "bad"},
                                 headers={"origin": "https://evil.example"})).status_code == 403
    assert calls[0]["api_key"] == "test-secret-key"
    assert calls[0]["api_base"] == "https://example.com/v1"
    assert "test-secret-key" not in (state / "latest.json").read_text()


async def test_model_failure_preserves_last_report(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    (state / "latest.json").write_text('{"content":"previous"}')
    monkeypatch.setattr("openagentic.agent.engine.litellm_chat",
                        AsyncMock(side_effect=RuntimeError("secret-key upstream error")))
    async with AsyncClient(transport=ASGITransport(app=create_app(notes, state, local())),
                           base_url="http://testserver") as client:
        r = await client.post("/api/run", json={})
        assert r.status_code == 502
        assert "secret-key" not in r.text
    assert (state / "latest.json").read_text() == '{"content":"previous"}'
