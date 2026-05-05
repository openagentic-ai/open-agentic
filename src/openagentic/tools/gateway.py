"""模块说明（中文）：`src/openagentic/tools/gateway.py`。

工具调用网关（ToolGateway）——对标 OpenAI 的 Harness 控制平面。

在工具执行前提供四步管控：
  1. 鉴权：检查调用者是否有权限执行此工具
  2. 审批：危险操作走审批门（复用 cli/permissions.py 的 allow/ask/deny）
  3. 执行：委托给 ToolSandbox 在隔离环境中运行
  4. 追踪：记录工具名、参数、结果、耗时到结构化日志

设计：
  - 环境变量 OPENAGENTIC_TOOL_GATEWAY=1 激活
  - 通过 ConversationEngine 的 executor callback 注入
  - ToolSandbox 实现可替换（默认 SubprocessSandbox）
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Awaitable

from openagentic.tools.sandbox import ToolResult, ToolSandbox, SubprocessSandbox

logger = logging.getLogger("openagentic.tools.gateway")

# ── 环境变量 ──────────────────────────────────────────────
ENABLED = os.environ.get("OPENAGENTIC_TOOL_GATEWAY", "0") == "1"
SANDBOX_TYPE = os.environ.get("OPENAGENTIC_TOOL_SANDBOX", "subprocess")

# 权限检查回调签名：async (tool_name: str, args: dict) -> bool | str
# 返回 True = 放行，str = 拒绝原因
PermissionChecker = Callable[[str, dict], Awaitable[bool | str]]


class ToolGateway:
    """工具调用网关——控制平面。

    用法::

        gw = ToolGateway(
            sandbox=SubprocessSandbox(),
            permission_checker=my_perm_checker,
        )

        # 作为 engine 的 executor callback 注入
        engine = ConversationEngine(
            ...,
            executor=gw.as_executor(),
        )

        # 或直接调用
        result = await gw.execute("run_command", {"command": "ls"})
    """

    def __init__(
        self,
        sandbox: ToolSandbox | None = None,
        permission_checker: PermissionChecker | None = None,
    ):
        self.sandbox = sandbox or SubprocessSandbox()
        self.permission_checker = permission_checker

    async def execute(self, tool_name: str, args: dict, timeout: float = 60.0) -> str:
        """执行工具调用（控制平面入口）。

        返回值是工具输出字符串（兼容 ConversationEngine 的 ToolExecutor 签名）。
        """
        start_ts = time.monotonic()

        # Step 1: 鉴权
        if self.permission_checker:
            result = await self.permission_checker(tool_name, args)
            if result is not True:
                reason = result if isinstance(result, str) else "permission denied"
                logger.warning("tool blocked by permission checker", tool=tool_name, reason=reason)
                return f"[Tool blocked: {reason}]"

        # Step 2: 审批（危险操作检查）
        # 复用 cli/permissions.py 的分类逻辑
        if _is_dangerous(tool_name, args):
            logger.info("dangerous tool call requested", tool=tool_name)

        # Step 3: 执行（委托沙箱）
        sandbox_result: ToolResult = await self.sandbox.execute(tool_name, args, timeout)

        # Step 4: 追踪
        duration_ms = (time.monotonic() - start_ts) * 1000
        logger.info(
            "tool executed",
            tool=tool_name,
            success=sandbox_result.success,
            duration_ms=round(duration_ms, 1),
            output_len=len(sandbox_result.output),
            truncated=sandbox_result.truncated,
        )

        if sandbox_result.error and not sandbox_result.success:
            return f"Error: {sandbox_result.error}"
        return sandbox_result.output

    def as_executor(self) -> Callable[[str, dict], Awaitable[str]]:
        """返回 async executor 回调，可直接注入 ConversationEngine。

        Returns:
            async (tool_name: str, args: dict) -> str
        """
        return self.execute


# ── 危险工具检测 ──────────────────────────────────────────

_DANGEROUS_COMMANDS = {
    "rm", "rmdir", "dd", "mkfs", "fdisk", "shutdown", "reboot",
    "chmod", "chown", "kill", "killall", "iptables", "ufw",
    "wget", "curl",  # 网络请求可能有 SSRF 风险
}


def _is_dangerous(tool_name: str, args: dict) -> bool:
    """检查工具调用是否可能危险。"""
    if tool_name == "run_command":
        command = args.get("command", args.get("cmd", ""))
        if not command:
            return False
        first_word = command.strip().split()[0] if command.strip() else ""
        # 检查命令名（处理 sudo 前缀）
        if first_word == "sudo" and len(command.strip().split()) > 1:
            first_word = command.strip().split()[1]
        return first_word in _DANGEROUS_COMMANDS

    if tool_name == "write_file":
        path = args.get("path", args.get("file", ""))
        # 写入系统目录视为危险
        dangerous_prefixes = ("/etc/", "/boot/", "/sys/", "/proc/", "~/.ssh/")
        for prefix in dangerous_prefixes:
            if path.startswith(prefix):
                return True

    return False
