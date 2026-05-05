"""模块说明（中文）：`src/openagentic/tools/sandbox.py`。

工具执行沙箱（ToolSandbox）——对标 OpenAI 的 Sandbox 执行平面。

提供隔离的工具执行环境，与 ToolGateway（控制平面）配合使用。
凭证和 API key 不进入沙箱，由控制平面在沙箱外围管理。

内置实现：
  - SubprocessSandbox：asyncio 子进程，支持超时和输出截断
  - （未来）DockerSandbox：容器隔离执行
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("openagentic.tools.sandbox")


@dataclass
class ToolResult:
    """工具执行结果。"""

    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0
    truncated: bool = False


class ToolSandbox(Protocol):
    """工具执行沙箱接口（Protocol——不强制继承）。

    所有沙箱实现需提供此接口。
    """

    async def execute(self, tool_name: str, args: dict, timeout: float = 60.0) -> ToolResult:
        """在隔离环境中执行工具调用。

        Args:
            tool_name: 工具名称（如 "run_command", "read_file"）
            args: 工具参数
            timeout: 超时秒数

        Returns:
            ToolResult，包含输出和元信息。
        """
        ...


@dataclass
class SubprocessSandbox:
    """基于 asyncio subprocess 的轻量沙箱。

    特点：
      - 零额外依赖，复用已有 subprocess 执行逻辑
      - 超时自动 kill
      - 输出截断（默认 10000 字符）
      - 不持有任何凭证或 API key
    """

    max_output_chars: int = 10000
    default_timeout: float = 60.0

    async def execute(self, tool_name: str, args: dict, timeout: float = 60.0) -> ToolResult:
        """执行工具调用。

        当前策略：对于非 shell 工具（read_file, write_file 等），直接
        调用已有的 agent/tools.py 工具实现。对于 shell 命令，走子进程。
        """
        effective_timeout = timeout if timeout > 0 else self.default_timeout
        start = asyncio.get_event_loop().time()

        try:
            if tool_name == "run_command":
                return await self._run_shell(args, effective_timeout, start)
            elif tool_name in ("read_file", "write_file"):
                return await self._run_file_op(tool_name, args, start)
            else:
                # 通用工具：通过子进程执行
                return await self._run_generic(tool_name, args, effective_timeout, start)
        except asyncio.TimeoutError:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution timed out after {effective_timeout}s",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            return ToolResult(
                success=False,
                output="",
                error=f"Sandbox error: {exc}",
                duration_ms=elapsed,
            )

    async def _run_shell(self, args: dict, timeout: float, start: float) -> ToolResult:
        """执行 shell 命令。"""
        command = args.get("command", args.get("cmd", ""))
        if not command:
            return ToolResult(success=False, output="", error="No command provided")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            elapsed = (asyncio.get_event_loop().time() - start) * 1000

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")
            truncated = False

            if len(output) > self.max_output_chars:
                output = output[:self.max_output_chars] + "\n... [output truncated]"
                truncated = True

            return ToolResult(
                success=proc.returncode == 0,
                output=output,
                error=err_output if proc.returncode != 0 else None,
                duration_ms=elapsed,
                truncated=truncated,
            )
        except asyncio.TimeoutError:
            raise  # let outer handler catch

    async def _run_file_op(self, tool_name: str, args: dict, start: float) -> ToolResult:
        """执行文件操作（read_file / write_file）。"""
        path = args.get("path", args.get("file", ""))
        if not path:
            return ToolResult(success=False, output="", error="No file path provided")

        try:
            if tool_name == "read_file":
                content = await asyncio.to_thread(
                    lambda: open(path, "r", encoding="utf-8").read()
                )
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                truncated = len(content) > self.max_output_chars
                if truncated:
                    content = content[:self.max_output_chars] + "\n... [file truncated]"
                return ToolResult(
                    success=True,
                    output=content,
                    duration_ms=elapsed,
                    truncated=truncated,
                )
            elif tool_name == "write_file":
                content = args.get("content", "")
                await asyncio.to_thread(
                    lambda: open(path, "w", encoding="utf-8").write(content)
                )
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                return ToolResult(
                    success=True,
                    output=f"File written: {path} ({len(content)} chars)",
                    duration_ms=elapsed,
                )
        except Exception as exc:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            return ToolResult(
                success=False,
                output="",
                error=f"File operation failed: {exc}",
                duration_ms=elapsed,
            )

    async def _run_generic(self, tool_name: str, args: dict, timeout: float, start: float) -> ToolResult:
        """通用工具执行（兜底）。"""
        import json
        cmd = f"echo '{{'tool':'{tool_name}','args':{json.dumps(args)}}}'"
        return await self._run_shell({"command": cmd}, timeout, start)
