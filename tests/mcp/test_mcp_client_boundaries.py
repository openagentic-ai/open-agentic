"""MCP client unit tests for success and boundary/error handling."""

from __future__ import annotations

import httpx
import pytest

from openagentic.mcp.client import MCPClient
from openagentic.mcp import client as mcp_client_mod


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://test/rpc")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=httpx.Response(self.status_code))

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, _url, json):
        self.last_payload = json
        return self._response


@pytest.mark.asyncio
async def test_mcp_call_returns_result(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse({"result": {"ok": True}}))
    monkeypatch.setattr(mcp_client_mod.httpx, "AsyncClient", lambda timeout: fake_client)

    client = MCPClient("http://mcp.local")
    result = await client.call("tools/list")
    assert result == {"ok": True}
    assert fake_client.last_payload["method"] == "tools/list"


@pytest.mark.asyncio
async def test_mcp_call_raises_runtime_error_on_json_rpc_error(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse({"error": {"message": "tool failed"}}))
    monkeypatch.setattr(mcp_client_mod.httpx, "AsyncClient", lambda timeout: fake_client)

    client = MCPClient("http://mcp.local")
    with pytest.raises(RuntimeError, match="tool failed"):
        await client.call("tools/call")


@pytest.mark.asyncio
async def test_mcp_call_propagates_http_status_error(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse({"error": {"message": "ignored"}}, status_code=502))
    monkeypatch.setattr(mcp_client_mod.httpx, "AsyncClient", lambda timeout: fake_client)

    client = MCPClient("http://mcp.local")
    with pytest.raises(httpx.HTTPStatusError):
        await client.call("tools/list")


@pytest.mark.asyncio
async def test_list_tools_returns_empty_when_payload_not_list(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse({"result": {"tools": "not-list"}}))
    monkeypatch.setattr(mcp_client_mod.httpx, "AsyncClient", lambda timeout: fake_client)

    client = MCPClient("http://mcp.local")
    tools = await client.list_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_invoke_tool_returns_content_field(monkeypatch):
    fake_client = _FakeAsyncClient(_FakeResponse({"result": {"content": {"text": "hello"}}}))
    monkeypatch.setattr(mcp_client_mod.httpx, "AsyncClient", lambda timeout: fake_client)

    client = MCPClient("http://mcp.local")
    payload = await client.invoke_tool("echo", {"message": "hello"})
    assert payload == {"text": "hello"}
