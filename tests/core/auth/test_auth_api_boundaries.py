"""Auth API integration tests with boundary/error paths."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.core.auth import service
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.main import app


@pytest.fixture
async def auth_api_client(monkeypatch):
    user_id = uuid.uuid4()
    fake_user = SimpleNamespace(
        id=user_id,
        email="user@example.com",
        hashed_password="hashed",
        display_name="User",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    state = {"user": fake_user}

    async def fake_db():
        yield object()

    async def fake_get_user_by_email(_db, email: str):
        if state["user"] and state["user"].email == email:
            return state["user"]
        return None

    async def fake_create_user(_db, email: str, _password: str, display_name: str | None):
        created = SimpleNamespace(
            id=uuid.uuid4(),
            email=email,
            hashed_password="hashed-new",
            display_name=display_name,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        state["user"] = created
        return created

    monkeypatch.setattr(service, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "create_user", fake_create_user)
    monkeypatch.setattr(service, "verify_password", lambda plain, _hashed: plain == "correct-pass")
    monkeypatch.setattr(service, "create_access_token", lambda user_id: (f"access-{user_id}", 3600))
    monkeypatch.setattr(service, "create_refresh_token", lambda user_id: f"refresh-{user_id}")

    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, state
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(auth_api_client):
    client, _ = auth_api_client
    resp = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123", "display_name": "User"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(auth_api_client):
    client, _ = auth_api_client
    resp = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-pass"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token(auth_api_client, monkeypatch):
    client, _ = auth_api_client
    monkeypatch.setattr(service, "decode_token", lambda _token: None)

    resp = await client.post("/api/auth/refresh", params={"token": "bad-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_refresh_rejects_non_refresh_token(auth_api_client, monkeypatch):
    client, _ = auth_api_client
    monkeypatch.setattr(service, "decode_token", lambda _token: {"sub": str(uuid.uuid4()), "type": "access"})

    resp = await client.post("/api/auth/refresh", params={"token": "access-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_me_returns_current_user(auth_api_client):
    client, state = auth_api_client

    async def fake_current_user():
        return state["user"]

    app.dependency_overrides[get_current_user] = fake_current_user
    try:
        resp = await client.get("/api/auth/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["email"] == "user@example.com"
    assert payload["is_active"] is True
