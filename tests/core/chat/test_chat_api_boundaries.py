"""Chat API integration tests for normal and error flows."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.core.chat import service
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.main import app


@pytest.fixture
async def chat_api_client(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        title="demo",
        model="deepseek/deepseek-chat",
        system_prompt=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def fake_current_user():
        return user

    async def fake_db():
        yield object()

    async def fake_get_conversation(_db, conv_id, _user_id):
        if conv_id == conv.id:
            return conv
        return None

    async def fake_get_messages(_db, _conv_id):
        return []

    async def fake_send_message(_db, conversation, message, model):
        return SimpleNamespace(
            id=uuid.uuid4(),
            role="assistant",
            content=f"echo:{message}",
            model=model or conversation.model,
            token_count_input=2,
            token_count_output=3,
            cost_usd=None,
            created_at=datetime.now(timezone.utc),
        )

    async def fake_send_message_stream(_db, _conversation, _message, _model):
        yield 'data: {"event":"token","data":"he"}\n\n'
        yield 'data: {"event":"done","data":"hello","usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'

    async def fake_delete_conversation(_db, conv_id, _user_id):
        return conv_id == conv.id

    monkeypatch.setattr(service, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(service, "get_messages", fake_get_messages)
    monkeypatch.setattr(service, "send_message", fake_send_message)
    monkeypatch.setattr(service, "send_message_stream", fake_send_message_stream)
    monkeypatch.setattr(service, "delete_conversation", fake_delete_conversation)

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, conv
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_message_non_stream_success(chat_api_client):
    client, conv = chat_api_client
    resp = await client.post(
        f"/api/conversations/{conv.id}/messages",
        json={"message": "hello", "stream": False},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["role"] == "assistant"
    assert payload["content"] == "echo:hello"


@pytest.mark.asyncio
async def test_send_message_stream_returns_sse(chat_api_client):
    client, conv = chat_api_client
    resp = await client.post(
        f"/api/conversations/{conv.id}/messages",
        json={"message": "hello", "stream": True},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert '"event":"done"' in resp.text


@pytest.mark.asyncio
async def test_send_message_returns_404_for_missing_conversation(chat_api_client):
    client, _ = chat_api_client
    resp = await client.post(
        f"/api/conversations/{uuid.uuid4()}/messages",
        json={"message": "hello", "stream": False},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_get_messages_returns_404_for_missing_conversation(chat_api_client):
    client, _ = chat_api_client
    resp = await client.get(f"/api/conversations/{uuid.uuid4()}/messages")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_delete_conversation_returns_404_for_missing_conversation(chat_api_client):
    client, _ = chat_api_client
    resp = await client.delete(f"/api/conversations/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversation not found"
