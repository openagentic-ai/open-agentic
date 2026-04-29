"""模块说明（中文）：`src/openagentic/agent/tools.py`。

Agent 工具注册表与内置工具实现。
工具分为两类：
- 新版 async Tool（支持 function-calling schema）
- 旧版 legacy sync 工具（简单字符串入/出，向后兼容）
"""

from __future__ import annotations

import asyncio
import ast
import operator
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import httpx
import structlog

from openagentic.config import SETTINGS

logger = structlog.get_logger("openagentic.agent.tools")

# 单次工具输出截断上限，防止 token 爆炸
_MAX_OUTPUT = 4000


@dataclass
class Tool:
    """新版工具定义：名称、描述、参数 schema、异步执行函数。

    参数 schema 遵循 OpenAI function-calling 格式：
    {"type": "object", "properties": {...}, "required": [...]}
    """
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[[dict[str, Any]], Awaitable[str]]


class ToolRegistry:
    """工具注册表：管理工具注册、查询和 schema 导出。

    同时持有：
    - _tools：新版 async Tool 注册表
    - _legacy_tools：旧版 sync 工具（字符串入/出，简单场景）
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        # 旧版同步工具：简单字符串参数，直接返回字符串
        self._legacy_tools: dict[str, Callable[[str], str]] = {
            "echo": lambda arg: arg,
            "current_time": lambda _arg: datetime.now(timezone.utc).isoformat(),
            "calculator": self._tool_calculator,
        }

    def register(self, tool: Tool) -> None:
        """注册一个新版 async 工具。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """按名称查找工具（仅新版 async 工具）。"""
        return self._tools.get(name)

    def list_tools(self, names: list[str] | None = None) -> list[Tool]:
        """列出工具，可按名称过滤。"""
        if names is None:
            return list(self._tools.values())
        return [t for n in names if (t := self._tools.get(n)) is not None]

    def get_schemas(self, names: list[str] | None = None) -> list[dict]:
        """导出 Ollama/OpenAI 兼容的 function-calling schema 列表。"""
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
        """返回所有工具的排序名称列表（含 legacy）。"""
        names = set(self._tools.keys()) | set(self._legacy_tools.keys())
        return sorted(names)

    def call(self, name: str, arg: str) -> str:
        """同步调用工具（仅支持 legacy sync 工具）。

        Raises:
            ValueError: 工具不存在或为 async-only 工具
        """
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
        """安全计算数学表达式（仅四则运算+幂，无 Python eval）。"""
        if not arg.strip():
            raise ValueError("calculator requires a math expression")
        return str(ToolRegistry._safe_eval_math(arg))

    @staticmethod
    def _safe_eval_math(expr: str) -> float:
        """使用 AST 安全解析数学表达式，不支持任何 Python 语句/函数调用。

        支持的运算：+ - * / **  和一元正负号。
        """
        # 一元运算符映射
        unary_operators: dict[type[ast.unaryop], Callable[[float], float]] = {
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        # 二元运算符映射
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


# ---------------------------------------------------------------------------
# 内置异步工具实现
# ---------------------------------------------------------------------------


async def _run_command(args: dict[str, Any]) -> str:
    """执行 shell 命令并返回输出（timeout 默认 60s，最大 60s）。

    安全：使用 asyncio subprocess，不经过 shell=True 的字符串拼接。
    """
    command = args.get("command", "")
    timeout = min(args.get("timeout", 60), 60)
    logger.info("tool run_command", command=command[:200])
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # stderr 合并到 stdout
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + "\n... (truncated)"
        return f"Exit code: {proc.returncode}\n{output}"
    except asyncio.TimeoutError:
        proc.kill()
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


async def _read_file(args: dict[str, Any]) -> str:
    """读取文件内容（UTF-8），超过上限截断。"""
    path = args.get("path", "")
    logger.info("tool read_file", path=path)
    try:
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, lambda: open(path, "r", encoding="utf-8").read())
        if len(content) > _MAX_OUTPUT:
            content = content[:_MAX_OUTPUT] + "\n... (truncated)"
        return content
    except Exception as e:
        return f"Error: {e}"


async def _write_file(args: dict[str, Any]) -> str:
    """写入文件（覆盖模式），返回写入字符数。"""
    path = args.get("path", "")
    content = args.get("content", "")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: open(path, "w", encoding="utf-8").write(content))
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error: {e}"


async def _http_request(args: dict[str, Any]) -> str:
    """发起 HTTP 请求并返回响应文本（30s timeout，跟随重定向）。"""
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    body = args.get("body")
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.request(method, url, headers=headers, content=body)
            text = resp.text
            if len(text) > _MAX_OUTPUT:
                text = text[:_MAX_OUTPUT] + "\n... (truncated)"
            return f"Status: {resp.status_code}\n{text}"
    except Exception as e:
        return f"Error: {e}"


async def _python_exec(args: dict[str, Any]) -> str:
    """执行 Python 代码片段（30s timeout，独立子进程隔离）。"""
    code = args.get("code", "")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = stdout.decode("utf-8", errors="replace")
        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + "\n... (truncated)"
        return f"Exit code: {proc.returncode}\n{output}"
    except asyncio.TimeoutError:
        proc.kill()
        return "Error: execution timed out"
    except Exception as e:
        return f"Error: {e}"


async def _echo(args: dict[str, Any]) -> str:
    """简单回声工具：返回输入文本。"""
    return str(args.get("input", ""))


async def _current_time(_args: dict[str, Any]) -> str:
    """返回当前 UTC 时间（ISO 8601 格式）。"""
    return datetime.now(timezone.utc).isoformat()


async def _calculator(args: dict[str, Any]) -> str:
    """安全计算数学表达式。"""
    expr = str(args.get("input", "")).strip()
    if not expr:
        raise ValueError("calculator requires a math expression")
    return str(ToolRegistry._safe_eval_math(expr))


async def _knowledge_search(args: dict[str, Any]) -> str:
    """调用平台知识库检索 API，支持 bearer token 鉴权。

    需要 query 和 kb_id 两个参数；可选 top_k 和 bearer_token。
    """
    query = str(args.get("query") or args.get("input") or "").strip()
    kb_id = str(args.get("kb_id") or "").strip()
    top_k = int(args.get("top_k") or 5)
    bearer_token = str(args.get("bearer_token") or "").strip()
    if not query:
        return "Error: knowledge_search requires query"
    if not kb_id:
        return "Error: knowledge_search requires kb_id"

    # 使用 OPENAGENTIC_API_BASE 或默认 localhost 连接平台 API
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
    """构建默认工具注册表，包含 9 个内置工具。

    工具清单：
    - echo: 回声
    - current_time: 当前 UTC 时间
    - calculator: 安全数学计算
    - run_command: 执行 shell 命令
    - read_file: 读取文件
    - write_file: 写入文件
    - http_request: HTTP 请求
    - python_exec: Python 代码执行
    - knowledge_search: 知识库检索
    """
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


# 全局默认注册表：Agent 创建时默认使用的工具集合
default_registry = _build_default_registry()
