"""Boundary tests for authentication dependencies."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from openagentic import deps


class _FakeResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _FakeDB:
    def __init__(self, user):
        self.user = user

    async def execute(self, _stmt):
        return _FakeResult(self.user)


@pytest.mark.asyncio
async def test_get_current_user_requires_credentials():
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(credentials=None, db=_FakeDB(None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(deps, "decode_token", lambda _token: None)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(credentials=credentials, db=_FakeDB(None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_sub(monkeypatch):
    monkeypatch.setattr(deps, "decode_token", lambda _token: {})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="missing-sub")
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(credentials=credentials, db=_FakeDB(None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_unknown_user(monkeypatch):
    monkeypatch.setattr(deps, "decode_token", lambda _token: {"sub": str(uuid.uuid4())})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(credentials=credentials, db=_FakeDB(None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found"


@pytest.mark.asyncio
async def test_get_current_user_returns_user(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), email="user@example.com")
    monkeypatch.setattr(deps, "decode_token", lambda _token: {"sub": str(user.id)})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    resolved = await deps.get_current_user(credentials=credentials, db=_FakeDB(user))
    assert resolved is user
