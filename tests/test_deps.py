"""Test dependency injection utilities."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from openagentic.deps import get_current_user, get_current_user_optional


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        """无 Authorization 头时应抛 401。"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None, db=AsyncMock())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """无效 JWT 应抛 401。"""
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token.here"
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, db=AsyncMock())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_user_not_found_raises_401(self):
        """JWT payload 无 sub 字段应抛 401（验证更稳健的路径）。"""
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt
        from datetime import datetime, timedelta, timezone
        from openagentic.config import SETTINGS

        # 无 sub 的 token —— 这是 get_current_user 明确会拒的路径
        payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        token = jwt.encode(payload, SETTINGS.JWT_SECRET_KEY, algorithm=SETTINGS.JWT_ALGORITHM)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, db=AsyncMock())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_payload_missing_sub_raises_401(self):
        """JWT payload 无 sub 字段应抛 401。"""
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt
        from datetime import datetime, timedelta, timezone
        from openagentic.config import SETTINGS

        payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        token = jwt.encode(payload, SETTINGS.JWT_SECRET_KEY, algorithm=SETTINGS.JWT_ALGORITHM)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, db=AsyncMock())
        assert exc_info.value.status_code == 401


class TestGetCurrentUserOptional:
    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """无鉴权头时应返回 None 而非抛异常。"""
        result = await get_current_user_optional(credentials=None, db=AsyncMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        """无效 token 应返回 None。"""
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid"
        )
        result = await get_current_user_optional(credentials=creds, db=AsyncMock())
        assert result is None
