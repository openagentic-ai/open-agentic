"""Boundary tests for LLM service and router endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from openagentic.core.llm import router, service


class _AsyncStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        async def _gen():
            for item in self._chunks:
                yield item

        return _gen()


@pytest.mark.asyncio
async def test_chat_completion_handles_missing_usage(monkeypatch):
    class _Store:
        def resolve_runtime(self, _model):
            return "openai/gpt-test", "https://api.example.com/v1", "sk-test"

    class _Resp:
        model = "openai/gpt-test"
        usage = None
        choices = [SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")]

    async def fake_acompletion(**_kwargs):
        return _Resp()

    monkeypatch.setattr(service, "get_provider_store", lambda: _Store())
    monkeypatch.setattr(service.litellm, "acompletion", fake_acompletion)

    payload = await service.chat_completion([{"role": "user", "content": "hi"}])
    assert payload["content"] == "ok"
    assert payload["usage"]["prompt_tokens"] == 0
    assert payload["usage"]["completion_tokens"] == 0
    assert payload["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_chat_completion_stream_emits_done_when_usage_missing(monkeypatch):
    class _Store:
        def resolve_runtime(self, _model):
            return "openai/gpt-test", "https://api.example.com/v1", "sk-test"

    chunk_token = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="he"), finish_reason=None)],
    )
    chunk_done = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")],
        usage=None,
    )

    async def fake_acompletion(**_kwargs):
        return _AsyncStream([chunk_token, chunk_done])

    monkeypatch.setattr(service, "get_provider_store", lambda: _Store())
    monkeypatch.setattr(service.litellm, "acompletion", fake_acompletion)

    events = []
    async for event in service.chat_completion_stream([{"role": "user", "content": "hi"}]):
        events.append(event)

    assert any('"event": "token"' in event for event in events)
    done_events = [event for event in events if '"event": "done"' in event]
    assert done_events
    assert '"prompt_tokens": 0' in done_events[-1]
    assert '"completion_tokens": 0' in done_events[-1]


@pytest.mark.asyncio
async def test_models_endpoint_falls_back_to_default_when_no_enabled_profiles(client, monkeypatch):
    class _Cfg:
        default_model = "deepseek/deepseek-chat"
        profiles = [SimpleNamespace(id="openai", enabled=False, models=["openai/gpt-4.1"])]

    class _Store:
        def get(self):
            return _Cfg()

    monkeypatch.setattr(router, "get_provider_store", lambda: _Store())
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["default_model"] == "deepseek/deepseek-chat"
    assert len(payload["models"]) == 1
    assert payload["models"][0]["id"] == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_provider_upsert_and_default_model_update(client, monkeypatch):
    state = {
        "default_model": "openai/gpt-4.1",
        "profiles": [],
        "public": {"default_model": "openai/gpt-4.1", "profiles": []},
    }

    class _Cfg:
        def __init__(self, data):
            self._data = data

        def to_public_dict(self):
            return self._data["public"]

    class _Store:
        def upsert_profile(self, **kwargs):
            state["public"] = {"default_model": state["default_model"], "profiles": [kwargs]}
            return _Cfg(state)

        def set_default_model(self, model):
            state["default_model"] = model
            state["public"] = {"default_model": model, "profiles": state["public"]["profiles"]}
            return _Cfg(state)

    monkeypatch.setattr(router, "get_provider_store", lambda: _Store())

    upsert_resp = await client.put(
        "/api/llm/providers/deepseek",
        json={
            "display_name": "DeepSeek",
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "models": ["deepseek/deepseek-chat"],
            "enabled": True,
        },
    )
    assert upsert_resp.status_code == 200
    assert upsert_resp.json()["profiles"][0]["profile_id"] == "deepseek"

    default_resp = await client.put("/api/llm/default-model", json={"model": "deepseek/deepseek-chat"})
    assert default_resp.status_code == 200
    assert default_resp.json()["default_model"] == "deepseek/deepseek-chat"
