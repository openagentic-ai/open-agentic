"""模块说明（中文）：`extensions/channels/channel_runner.py`。

渠道运行器：飞书/企微等渠道的共享 AI 回复逻辑。

提取自 ``scripts/run_feishu_ws.py``，供各渠道独立运行脚本复用。
与 core 完全解耦——只依赖 ConversationEngine + identity，不依赖 FastAPI/PostgreSQL。
"""

from __future__ import annotations

import asyncio
import os
import structlog
import subprocess
from typing import Any

logger = structlog.get_logger("openagentic.channels.runner")

MAX_HISTORY = 20
MAX_TOOL_ITERATIONS = 15

# ── 公共工具定义 ──────────────────────────────────────────────────────────

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在服务器上执行终端命令并返回输出。用于运行脚本、查看系统状态、git操作等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取服务器上的文件内容。用于查看代码、配置、日志等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径（绝对路径）"},
                    "max_lines": {"type": "integer", "description": "最大读取行数，默认200"},
                },
                "required": ["path"],
            },
        },
    },
]

LARK_TOOL = {
    "type": "function",
    "function": {
        "name": "lark_cli",
        "description": (
            "飞书全能工具，覆盖几乎所有飞书 API。将用户意图翻译为 lark-cli 命令参数即可。\n\n"
            "核心能力分类：\n"
            "一、日程管理 — 查看今日日程、查询时段事件、创建/修改/删除日程\n"
            "二、文档处理 — 创建/读取/修改/搜索飞书文档、插入图片和文件、下载媒体\n"
            "三、多维表格 — 记录查询/搜索/批量创建/批量更新/删除/upsert、建表/加字段/创建表单/工作流/仪表盘\n"
            "四、消息与群聊 — 发送/回复消息、创建/搜索群、查询聊天记录/搜索消息\n"
            "五、审批流程 — 查询/同意/拒绝/转交/催办审批任务、管理审批实例\n"
            "六、通讯录 — 搜索用户\n"
            "七、云盘 — 文件上传/下载/权限管理\n"
            "八、邮箱 — 邮件读写/草稿管理/联系人管理\n"
            "九、任务管理 — 任务和任务列表的创建/修改/删除\n"
            "十、知识库 — Wiki 空间和节点的管理\n"
            "十一、办公套件 — 电子表格创建/读写、幻灯片创建/修改/读取、白板创建/编辑、会议纪要搜索/读取\n"
            "十二、视频会议（只读） — 搜索会议、查询录制/笔记\n"
            "十三、人力资源 — 考勤查询打卡记录、OKR目标/关键结果/对齐管理\n"
            "十四、通用能力 — 调用飞书所有公开 API（lark-cli 兜底）\n"
            "十五、服务器能力 — 执行 Shell 命令（脚本/Git/系统管理）、读写服务器文件（代码/配置/日志）\n"
            "⚠️ 不要假设不能做——先用 lark-cli 试试，几乎所有飞书 API 都能调。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "lark-cli 命令参数，如 [\"calendar\", \"+agenda\"]",
                },
            },
            "required": ["args"],
        },
    },
}

# ── 工具执行 ──────────────────────────────────────────────────────────────


async def execute_tool(name: str, args: dict) -> str:
    """执行工具调用，返回结果字符串。"""
    if name == "run_command":
        return await _run_command(args.get("command", ""))
    elif name == "read_file":
        return await _read_file(args.get("path", ""), args.get("max_lines", 200))
    elif name == "lark_cli":
        return await _run_lark_cli(args.get("args", []))
    return f"未知工具: {name}"


async def _run_command(command: str) -> str:
    cmd = command.strip()
    if not cmd:
        return "错误：命令为空"
    logger.info("[TOOL] run_command", command=cmd[:200])
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        result = out or err or "(无输出)"
        if len(result) > 4000:
            result = result[:4000] + "\n... (输出截断)"
        return result
    except asyncio.TimeoutError:
        return "错误：命令执行超时 (30s)"


async def _read_file(path: str, max_lines: int = 200) -> str:
    fpath = os.path.expanduser(path)
    logger.info("[TOOL] read_file", path=fpath)
    dangerous = ["/etc/shadow", "/etc/passwd", "~/.ssh", "id_rsa", ".env", "secret"]
    if any(d in fpath for d in dangerous):
        return "错误：出于安全考虑，禁止读取此文件"
    try:
        if not os.path.isfile(fpath):
            return f"错误：文件不存在 — {fpath}"
        size = os.path.getsize(fpath)
        if size > 2 * 1024 * 1024:
            return f"错误：文件过大 ({size / 1024:.0f}KB)"
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            lines = [next(f) for _ in range(max_lines)]
        return "".join(lines)
    except Exception as e:
        return f"读取失败：{e}"


async def _run_lark_cli(args: list[str]) -> str:
    cmd = ["lark-cli"] + args
    logger.info("[TOOL] lark-cli", cmd=" ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        result = out or err or "(无输出)"
        if len(result) > 4000:
            result = result[:4000] + "\n... (输出截断)"
        return result
    except asyncio.TimeoutError:
        return "错误：lark-cli 执行超时 (30s)"
    except FileNotFoundError:
        return "错误：lark-cli 未安装"


# ── AI 回复（带工具调用循环）─────────────────────────────────────────────


class ChannelAIService:
    """渠道共享 AI 服务：对话引擎 + 历史管理。

    每个 chat_id 独立维护历史，支持多轮对话。
    """

    def __init__(
        self,
        *,
        extra_tools: list[dict] | None = None,
        channel_hints: list[str] | None = None,
    ):
        model = os.getenv("OPENAGENTIC_MODEL") or os.getenv(
            "LITELLM_DEFAULT_MODEL", "deepseek/deepseek-v4-flash"
        )
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_BASE_URL") if model.startswith("openai/") else None

        tools = list(BASE_TOOLS)
        if extra_tools:
            tools.extend(extra_tools)

        from openagentic.identity import build_system_prompt
        system_prompt = build_system_prompt(list(channel_hints) if channel_hints else None)

        from openagentic.agent.engine import ConversationEngine
        self.engine = ConversationEngine(
            model=model,
            api_key=api_key,
            api_base=api_base,
            tools=tools,
            system_prompt=system_prompt,
            executor=execute_tool,
            max_iterations=MAX_TOOL_ITERATIONS,
        )
        self._histories: dict[str, list[dict]] = {}

    async def reply(self, user_text: str, chat_id: str) -> str:
        """处理一条用户消息，返回 AI 回复。"""
        history = self._histories.setdefault(chat_id, [])
        messages = [
            {"role": "system", "content": self.engine.system_prompt},
            *history[-MAX_HISTORY:],
            {"role": "user", "content": user_text},
        ]
        try:
            reply = await self.engine.chat(messages)
        except Exception as e:
            logger.exception("LLM call failed")
            reply = f"抱歉，AI 调用失败：{e}"

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        self._histories[chat_id] = history[-MAX_HISTORY:]
        return reply
