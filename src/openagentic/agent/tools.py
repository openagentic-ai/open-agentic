"""模块说明（中文）：`src/openagentic/agent/tools.py`。\n\n该文件属于 Agent 模块，处理智能体定义、执行与工具调用。\n"""

from __future__ import annotations

import asyncio
import ast
import operator
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import httpx

from openagentic.config import SETTINGS


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
        self._legacy_tools: dict[str, Callable[[str], str]] = {
            "echo": lambda arg: arg,
            "current_time": lambda _arg: datetime.now(timezone.utc).isoformat(),
            "calculator": self._tool_calculator,
        }

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

    def list_tool_names(self) -> list[str]:
        names = set(self._tools.keys()) | set(self._legacy_tools.keys())
        return sorted(names)

    def call(self, name: str, arg: str) -> str:
        legacy = self._legacy_tools.get(name)
        if legacy:
            return legacy(arg)

        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        raise ValueError(
            f"Tool '{name}' only supports async calls; use function-calling execution path."
        )

    def _tool_calculator(self, arg: str) -> str:
        if not arg.strip():
            raise ValueError("calculator requires a math expression")
        return str(self._safe_eval_math(arg))

    def _safe_eval_math(self, expr: str) -> float:
        unary_operators: dict[type[ast.unaryop], Callable[[float], float]] = {
            ast.USub: operator.neg,
        }
        binary_operators: dict[type[ast.operator], Callable[[float, float], float]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
        }

        def _eval(node: ast.AST) -> float:
            if isinstance(node, ast.Num):  # pragma: no cover - py<3.8 compatibility path
                if isinstance(node.n, (int, float)):
                    return float(node.n)
                raise ValueError("Unsupported number type")
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.UnaryOp) and type(node.op) in unary_operators:
                unary_op = unary_operators[type(node.op)]
                return unary_op(_eval(node.operand))
            if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
                binary_op = binary_operators[type(node.op)]
                return binary_op(_eval(node.left), _eval(node.right))
            raise ValueError("Unsupported expression")

        parsed = ast.parse(expr, mode="eval")
        return _eval(parsed.body)


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


async def _echo(args: dict[str, Any]) -> str:
    return str(args.get("input", ""))


async def _current_time(_args: dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat()


async def _calculator(args: dict[str, Any]) -> str:
    expr = str(args.get("input", "")).strip()
    if not expr:
        raise ValueError("calculator requires a math expression")
    registry = ToolRegistry()
    return str(registry._safe_eval_math(expr))


async def _knowledge_search(args: dict[str, Any]) -> str:
    query = str(args.get("query") or args.get("input") or "").strip()
    kb_id = str(args.get("kb_id") or "").strip()
    top_k = int(args.get("top_k") or 5)
    bearer_token = str(args.get("bearer_token") or "").strip()
    if not query:
        return "Error: knowledge_search requires query"
    if not kb_id:
        return "Error: knowledge_search requires kb_id"

    api_base = (SETTINGS.OPENAGENTIC_API_BASE or "http://127.0.0.1:8000").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{api_base}/api/knowledge/{kb_id}/search",
                headers=headers,
                json={"query": query, "top_k": top_k, "rerank": True, "rerank_top_n": max(top_k, 10)},
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        return f"knowledge_search failed: {exc}"

    if not rows:
        return "knowledge_search: no results"
    lines = ["knowledge_search results:"]
    for item in rows[:top_k]:
        score = float(item.get("rerank_score") or item.get("score") or 0.0)
        content = str(item.get("content", ""))[:180]
        lines.append(f"- score={score:.4f} content={content}")
    return "\n".join(lines)


def _build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(Tool(
        name="echo",
        description="Echo the input text.",
        parameters={
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Text to echo"}},
            "required": ["input"],
        },
        execute=_echo,
    ))

    registry.register(Tool(
        name="current_time",
        description="Get current UTC time in ISO format.",
        parameters={"type": "object", "properties": {}},
        execute=_current_time,
    ))

    registry.register(Tool(
        name="calculator",
        description="Evaluate a basic arithmetic expression.",
        parameters={
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Math expression"}},
            "required": ["input"],
        },
        execute=_calculator,
    ))

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

    registry.register(Tool(
        name="knowledge_search",
        description="Search a knowledge base with vector retrieval and reranking.",
        parameters={
            "type": "object",
            "properties": {
                "kb_id": {"type": "string", "description": "Knowledge base ID"},
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Top-K results", "default": 5},
                "bearer_token": {"type": "string", "description": "Optional API bearer token"},
            },
            "required": ["kb_id", "query"],
        },
        execute=_knowledge_search,
    ))

    return registry


default_registry = _build_default_registry()
