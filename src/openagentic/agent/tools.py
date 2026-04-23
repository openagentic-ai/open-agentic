"""Built-in tool registry for agent execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import httpx


@dataclass
class Tool:
    """A tool that an agent can use."""
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[[dict[str, Any]], Awaitable[str]]


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self, names: list[str] | None = None) -> list[Tool]:
        if names is None:
            return list(self._tools.values())
        return [t for n in names if (t := self._tools.get(n)) is not None]

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        """Return tool schemas in Ollama function-calling format."""
        tools = self.list_tools(names)
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]


async def _run_command(args: dict[str, Any]) -> str:
    command = args.get("command", "")
    timeout = min(args.get("timeout", 60), 60)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode(errors="replace")
        if len(output) > 4000:
            output = output[:4000] + "\n... (truncated)"
        return f"Exit code: {proc.returncode}\n{output}"
    except asyncio.TimeoutError:
        proc.kill()
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


async def _read_file(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    try:
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, lambda: open(path, "r").read())
        if len(content) > 4000:
            content = content[:4000] + "\n... (truncated)"
        return content
    except Exception as e:
        return f"Error: {e}"


async def _write_file(args: dict[str, Any]) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: open(path, "w").write(content))
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error: {e}"


async def _http_request(args: dict[str, Any]) -> str:
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    body = args.get("body")
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.request(method, url, headers=headers, content=body)
            text = resp.text
            if len(text) > 4000:
                text = text[:4000] + "\n... (truncated)"
            return f"Status: {resp.status_code}\n{text}"
    except Exception as e:
        return f"Error: {e}"


async def _python_exec(args: dict[str, Any]) -> str:
    code = args.get("code", "")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = stdout.decode(errors="replace")
        if len(output) > 4000:
            output = output[:4000] + "\n... (truncated)"
        return f"Exit code: {proc.returncode}\n{output}"
    except asyncio.TimeoutError:
        proc.kill()
        return "Error: execution timed out"
    except Exception as e:
        return f"Error: {e}"


def _build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(Tool(
        name="run_command",
        description="Execute a shell command and return the output.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (max 60)", "default": 60},
            },
            "required": ["command"],
        },
        execute=_run_command,
    ))

    registry.register(Tool(
        name="read_file",
        description="Read the contents of a file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
            },
            "required": ["path"],
        },
        execute=_read_file,
    ))

    registry.register(Tool(
        name="write_file",
        description="Write content to a file, creating or overwriting it.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        execute=_write_file,
    ))

    registry.register(Tool(
        name="http_request",
        description="Make an HTTP request and return the response.",
        parameters={
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "HTTP method", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                "url": {"type": "string", "description": "Request URL"},
                "headers": {"type": "object", "description": "Request headers", "default": {}},
                "body": {"type": "string", "description": "Request body"},
            },
            "required": ["url"],
        },
        execute=_http_request,
    ))

    registry.register(Tool(
        name="python_exec",
        description="Execute a Python code snippet and return the output.",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
        execute=_python_exec,
    ))

    return registry


default_registry = _build_default_registry()
