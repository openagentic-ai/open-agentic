"""DefaultIdentityResolver 测试。

monkeypatch channels.bindings 三个底层函数,不碰真实 DB。
覆盖路径:
- 直接命中(resolve_user_id 返回)
- auto_bind 命中(飞书自动绑定)
- fallback 命中(env)
- 全部 miss → None
- auto_bind=False 时不触发自动绑定
- 非飞书 adapter 不触发 auto_bind(只飞书有 lookup_name)
- 空参数 → None
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from openagentic.application.identity_default import DefaultIdentityResolver


_BIND_PATH = "openagentic.channels.bindings"


@pytest.mark.asyncio
async def test_resolve_direct_hit():
    direct_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=direct_uid)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock()) as auto_bind, \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=None) as fb:
        r = DefaultIdentityResolver()
        out = await r.resolve("feishu", "ou_abc")
        assert out == str(direct_uid)
        auto_bind.assert_not_called()
        fb.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_auto_bind_feishu():
    bound_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock(return_value=bound_uid)) as auto_bind, \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=None) as fb:
        r = DefaultIdentityResolver()
        out = await r.resolve("feishu", "ou_new")
        assert out == str(bound_uid)
        auto_bind.assert_awaited_once()
        fb.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_fallback_when_no_binding():
    fb_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=fb_uid):
        r = DefaultIdentityResolver()
        out = await r.resolve("feishu", "ou_x")
        assert out == str(fb_uid)


@pytest.mark.asyncio
async def test_resolve_all_miss_returns_none():
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=None):
        r = DefaultIdentityResolver()
        out = await r.resolve("feishu", "ou_x")
        assert out is None


@pytest.mark.asyncio
async def test_resolve_auto_bind_false_skips_binding():
    fb_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock()) as auto_bind, \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=fb_uid):
        r = DefaultIdentityResolver()
        out = await r.resolve("feishu", "ou_x", auto_bind=False)
        assert out == str(fb_uid)
        auto_bind.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_non_feishu_skips_auto_bind():
    fb_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.resolve_user_id", new=AsyncMock(return_value=None)), \
         patch(f"{_BIND_PATH}.auto_bind_feishu_user", new=AsyncMock()) as auto_bind, \
         patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=fb_uid):
        r = DefaultIdentityResolver()
        out = await r.resolve("wecom", "wc_x")
        assert out == str(fb_uid)
        auto_bind.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_empty_params_returns_none():
    r = DefaultIdentityResolver()
    assert await r.resolve("", "x") is None
    assert await r.resolve("feishu", "") is None


@pytest.mark.asyncio
async def test_fallback_user_id_present():
    fb_uid = uuid.uuid4()
    with patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=fb_uid):
        r = DefaultIdentityResolver()
        assert await r.fallback_user_id() == str(fb_uid)


@pytest.mark.asyncio
async def test_fallback_user_id_absent():
    with patch(f"{_BIND_PATH}.fallback_bot_user_id", return_value=None):
        r = DefaultIdentityResolver()
        assert await r.fallback_user_id() is None
