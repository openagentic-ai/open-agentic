"""模块说明（中文）：`src/openagentic/mcp/client.py`。\n\n该文件属于 MCP 集成模块，处理协议调用与工具桥接。\n"""

from __future__ import annotations

from typing import Any

import httpx


class MCPClient:
    """Simple async MCP client over HTTP JSON-RPC."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": "openagentic-phase2",
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/rpc", json=payload)
            response.raise_for_status()
            data = response.json()
        if "error" in data:
            message = data["error"].get("message", "MCP call failed")
            raise RuntimeError(message)
        return data.get("result", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.call("tools/list")
        tools = result.get("tools", [])
        if isinstance(tools, list):
            return tools
        return []

    async def invoke_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = await self.call("tools/call", {"name": name, "arguments": arguments or {}})
        return result.get("content")

