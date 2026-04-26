"""Test RequestContextMiddleware."""

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from openagentic.observability.middleware import RequestContextMiddleware


def _make_app():
    app_ = FastAPI()
    app_.add_middleware(RequestContextMiddleware)

    @app_.get("/ping")
    async def ping():
        from openagentic.tenant import get_current_request_id
        return {"request_id": get_current_request_id()}

    return app_


class TestRequestContextMiddleware:
    """验证中间件对 request_id/tenant_id 的注入与透传。"""

    @pytest.mark.asyncio
    async def test_generates_request_id_when_missing(self):
        """没有 X-Request-ID 头时，中间件应自动生成 request_id。"""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"]  # 非空字符串
        assert len(data["request_id"]) == 32  # uuid4 hex

    @pytest.mark.asyncio
    async def test_passthrough_request_id(self):
        """有 X-Request-ID 头时，中间件应透传并回写响应头。"""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ping", headers={"X-Request-ID": "my-custom-id"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "my-custom-id"
        assert resp.headers.get("x-request-id") == "my-custom-id"

    @pytest.mark.asyncio
    async def test_ignores_non_http_scopes(self):
        """非 HTTP scope（如 websocket）应直接 pass。"""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ping")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_request_id_header(self):
        """响应头中必须包含 x-request-id。"""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ping")
        assert "x-request-id" in resp.headers
