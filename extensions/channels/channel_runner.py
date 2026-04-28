"""模块说明（中文）：`extensions/channels/channel_runner.py`。

渠道运行器：飞书/企微等渠道的共享 AI 回复逻辑。

提取自 ``scripts/run_feishu_ws.py``，供各渠道独立运行脚本复用。
与 core 完全解耦——只依赖 ConversationEngine + identity，不依赖 FastAPI/PostgreSQL。
"""

from __future__ import annotations

import asyncio
import contextvars
import os
import structlog
import subprocess
from typing import Any

logger = structlog.get_logger("openagentic.channels.runner")

# 预加载 SQLAlchemy 模型，确保 mapper 初始化时所有关联类已就绪。
# 飞书渠道不经过 main.py 的 import 链，不走 FastAPI lifespan，
# 因此必须在此处显式加载，否则 _current_user_id 触发 _init_models
# 会因 Conversation 未 import 而抛 InvalidRequestError。
import openagentic.core.chat.models as _chat_models  # noqa: F401

# 当前请求的渠道身份——由 ChannelAIService.reply() 入口设置，
# 工具执行时（execute_tool 内）按需读取以解析 OpenAgentic User。
# 用 contextvars 而不是改 execute_tool 签名，避免破坏既有 ConversationEngine 契约。
_current_platform: contextvars.ContextVar[str] = contextvars.ContextVar(
    "channel_platform", default=""
)
_current_sender_open_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "channel_sender_open_id", default=""
)

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

WORKFLOW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_workflows",
            "description": (
                "列出当前 bot 归属用户名下的 DAG 工作流（含名称、描述、ID、是否启用）。"
                "用户问'有什么工作流/流程/SOP'，或想触发某个流程时，先调这个查可用列表。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_workflow",
            "description": (
                "创建新的 DAG 工作流。用户描述流程需求后，你按规范构造 definition（nodes + edges），调此工具创建。\n\n"
                "支持的节点类型（type）：\n"
                "- llm — 调用 LLM 处理/生成文本（config: {prompt, model, temperature}）\n"
                "- tool — 执行服务器命令（config: {command}）\n"
                "- feishu — 飞书操作：发消息/建文档/建表格/日程/审批等（config: {action, ...}）\n"
                "- wecom — 企业微信操作（config: {action, ...}）\n"
                "- value — 静态值/常量注入（config: {value}）\n"
                "- approval — 人工审批节点（config: {approvers, message}）\n"
                "- human_input — 等待用户输入（config: {prompt, timeout_seconds}）\n\n"
                "definition 结构：{\"nodes\": [{每个 node 必须有 id/type/label/config}], \"edges\": [{\"from\": \"node_id\", \"to\": \"node_id\"}]}\n"
                "每个 node 必须有：id（唯一字符串）、type（上述类型之一）、label（显示名）、config（dict，类型相关配置）。\n"
                "edges 表示执行顺序，不能有环。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "工作流名称"},
                    "description": {"type": "string", "description": "简要描述这个工作流做什么"},
                    "definition": {"type": "object", "description": "DAG 定义：{\"nodes\": [...], \"edges\": [...]}"},
                },
                "required": ["name", "description", "definition"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_workflow",
            "description": (
                "启动指定 DAG 工作流（异步）——立即返回 run_id，DAG 在后台跑。"
                "workflow_id 必须是 UUID，先用 list_workflows 获取；"
                "input_data 是工作流定义里 {{input.xxx}} 引用的字段。"
                "需要查进度/拿结果 → 调 query_workflow_run(run_id)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow UUID"},
                    "input_data": {
                        "type": "object",
                        "description": "工作流输入字段，对应定义里的 {{input.xxx}}",
                    },
                },
                "required": ["workflow_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_workflow_run",
            "description": (
                "查询某次工作流执行的状态与结果。返回 status (pending/running/suspended/completed/failed/cancelled)、output、trace。"
                "适合用户问'刚才的工作流跑完了吗''结果是什么'时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Workflow run UUID（由 run_workflow 返回）"},
                },
                "required": ["run_id"],
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
    elif name == "list_workflows":
        return await _list_workflows()
    elif name == "create_workflow":
        return await _create_workflow(
            args.get("name", ""),
            args.get("description", ""),
            args.get("definition") or {},
        )
    elif name == "run_workflow":
        return await _run_workflow(
            args.get("workflow_id", ""),
            args.get("input_data") or {},
        )
    elif name == "query_workflow_run":
        return await _query_workflow_run(args.get("run_id", ""))
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


# ── Workflow 工具实现 ────────────────────────────────────────────────────
# 用户解析路径（user_channel_bindings 优先 → env 兜底）：
#   1. 当前请求的 (platform, sender_open_id) 命中 user_channel_bindings → 该 User
#   2. 未命中时回退 env OPENAGENTIC_BOT_USER_ID（保留单租户老部署兼容性）
#   3. 都没有 → 工具拒绝执行


async def _current_user_id():
    """解析当前渠道请求归属的 OpenAgentic User UUID。

    优先按 (platform, sender_open_id) 反查 user_channel_bindings；
    未命中且配置了 env OPENAGENTIC_BOT_USER_ID 时走 env 兜底。
    """
    from openagentic.channels.bindings import resolve_user_id_with_fallback
    platform = _current_platform.get("")
    sender_open_id = _current_sender_open_id.get("")
    return await resolve_user_id_with_fallback(platform, sender_open_id)


async def _create_workflow(name: str, description: str, definition: dict) -> str:
    """创建新的 DAG 工作流。"""
    import json as _json

    user_id = await _current_user_id()
    if user_id is None:
        return (
            "抱歉，未能识别你的身份，请稍后重试。"
        )
    if not name:
        return "错误：缺少工作流名称"
    if not definition.get("nodes"):
        return "错误：definition 必须包含 nodes 数组"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        from openagentic.workflow.schemas import WorkflowCreate
        async with async_session() as db:
            body = WorkflowCreate(name=name, description=description, definition=definition)
            workflow = await wf_service.create_workflow(db, user_id, body)
            wf_id = workflow.id
            wf_name = workflow.name
            await db.commit()
        return _json.dumps({
            "id": str(wf_id),
            "name": wf_name,
            "status": "created",
            "note": "工作流已创建。用 list_workflows 查看全部，用 run_workflow 启动执行。",
        }, ensure_ascii=False, indent=2)
    except ValueError as e:
        return f"工作流定义校验失败：{e}"
    except Exception as e:
        logger.exception("create_workflow failed")
        return f"创建工作流失败：{e}"


async def _list_workflows() -> str:
    """列出当前渠道用户名下的所有 workflows。"""
    user_id = await _current_user_id()
    if user_id is None:
        return (
            "抱歉，未能识别你的身份，请稍后重试。"
        )
    try:
        # 延迟 import 避免在未启用 workflow 时拉起 DB/ORM
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        async with async_session() as db:
            wfs = await wf_service.list_workflows(db, user_id)
        if not wfs:
            return "(无可用工作流)"
        lines = []
        for w in wfs:
            tag = "" if w.is_active else " [已停用]"
            desc = (w.description or "").strip() or "(无)"
            lines.append(f"- {w.name}{tag}\n  ID: {w.id}\n  描述: {desc}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("list_workflows failed")
        return f"查询工作流失败：{e}"


async def _run_workflow(workflow_id: str, input_data: dict) -> str:
    """启动 workflow（异步）——立即返回 run_id，不等执行完成。

    调用方拿到 run_id 后通过 query_workflow_run 查进度/结果，避免阻塞渠道回复。
    """
    import json as _json
    import uuid as _uuid

    user_id = await _current_user_id()
    if user_id is None:
        return (
            "抱歉，未能识别你的身份，请稍后重试。"
        )
    if not workflow_id:
        return "错误：缺少 workflow_id"
    try:
        wf_uuid = _uuid.UUID(str(workflow_id))
    except (ValueError, TypeError):
        return f"错误：workflow_id 不是合法 UUID — {workflow_id}"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        from openagentic.workflow.runtime import runtime
        async with async_session() as db:
            workflow = await wf_service.get_workflow(db, wf_uuid, user_id)
            if not workflow:
                return f"错误：找不到工作流 {workflow_id}（或不属于当前用户）"
            if not workflow.is_active:
                return f"错误：工作流 {workflow.name} 已停用"
            run = await wf_service.create_run(db, workflow, input_data or {})
            run_id = run.id
            wf_id = workflow.id
            wf_name = workflow.name
            await db.commit()

        # 后台执行——execute_run_by_id 自带 async_session，不污染当前连接
        runtime.start(run_id, wf_service.execute_run_by_id(run_id, wf_id, user_id))

        return _json.dumps({
            "run_id": str(run_id),
            "workflow": wf_name,
            "status": "started",
            "note": "工作流已在后台启动。用 query_workflow_run(run_id) 查进度。",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("run_workflow failed")
        return f"启动工作流失败：{e}"


async def _query_workflow_run(run_id: str) -> str:
    """查询 workflow run 状态。"""
    import json as _json
    import uuid as _uuid

    user_id = await _current_user_id()
    if user_id is None:
        return "错误：当前账号未绑定 OpenAgentic 用户"
    if not run_id:
        return "错误：缺少 run_id"
    try:
        run_uuid = _uuid.UUID(str(run_id))
    except (ValueError, TypeError):
        return f"错误：run_id 不是合法 UUID — {run_id}"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        async with async_session() as db:
            run = await wf_service.get_run(db, run_uuid, user_id)
        if not run:
            return f"错误：找不到 run {run_id}（或不属于当前用户）"

        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        node_states = run.node_states or {}
        result = {
            "run_id": str(run.id),
            "status": status,
            "output": (run.output_data or {}).get("result"),
            "trace": node_states.get("trace", []),
        }
        # suspended 时附带 _waiting_for 信息，便于上游知道下一步动作
        if status == "suspended" and "_waiting_for" in node_states:
            result["waiting_for"] = node_states["_waiting_for"]
        out = _json.dumps(result, ensure_ascii=False, default=str, indent=2)
        if len(out) > 4000:
            out = out[:4000] + "\n... (输出截断)"
        return out
    except Exception as e:
        logger.exception("query_workflow_run failed")
        return f"查询失败：{e}"


# ── AI 回复（带工具调用循环）─────────────────────────────────────────────


class ChannelAIService:
    """渠道共享 AI 服务：对话引擎 + 四层记忆 + 历史管理。

    每个 chat_id 独立维护历史，支持多轮对话。
    四层记忆（Working/Core/Episodic/Procedural）与 CLI 完全复用。
    """

    def __init__(
        self,
        *,
        extra_tools: list[dict] | None = None,
        channel_hints: list[str] | None = None,
    ):
        self._model = os.getenv("OPENAGENTIC_MODEL") or os.getenv(
            "LITELLM_DEFAULT_MODEL", "deepseek/deepseek-v4-flash"
        )
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._api_base = os.getenv("OPENAI_BASE_URL") if self._model.startswith("openai/") else None

        tools = list(BASE_TOOLS)
        if extra_tools:
            tools.extend(extra_tools)
        # workflow 工具始终挂载——是否能用取决于 sender 在 user_channel_bindings
        # 是否有绑定（或 env OPENAGENTIC_BOT_USER_ID 兜底）。未绑定时工具自身返回提示。
        tools.extend(WORKFLOW_TOOLS)

        from openagentic.identity import build_system_prompt
        system_prompt = build_system_prompt(list(channel_hints) if channel_hints else None)

        # Core memory：启动时注入 system prompt
        try:
            from openagentic.cli.prompt import build_core_memory_section
            core = build_core_memory_section(limit=20)
            if core:
                system_prompt += "\n" + core
        except Exception as exc:
            logger.warning("core memory injection failed", error=str(exc))

        from openagentic.agent.engine import ConversationEngine
        self.engine = ConversationEngine(
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
            tools=tools,
            system_prompt=system_prompt,
            executor=execute_tool,
            max_iterations=MAX_TOOL_ITERATIONS,
        )
        self._histories: dict[str, list[dict]] = {}

    async def reply(
        self,
        user_text: str,
        chat_id: str,
        *,
        platform: str = "",
        sender_open_id: str = "",
    ) -> str:
        """处理一条用户消息，返回 AI 回复。

        每轮自动注入 episodic + procedural memory，触发 working memory 压缩。
        platform/sender_open_id 用于在工具执行（如 run_workflow）时按 user_channel_bindings 解析归属用户。
        """
        # 把渠道身份塞到 contextvars，供本次 LLM 调用链内的工具读取
        _platform_token = _current_platform.set(platform)
        _sender_token = _current_sender_open_id.set(sender_open_id)
        try:
            return await self._reply_inner(user_text, chat_id)
        finally:
            _current_platform.reset(_platform_token)
            _current_sender_open_id.reset(_sender_token)

    async def _reply_inner(self, user_text: str, chat_id: str) -> str:
        from openagentic.memory.manager import (
            MemoryManager,
            working_memory_compressible,
            compress_working_memory,
        )
        history = self._histories.setdefault(chat_id, [])
        messages = [
            {"role": "system", "content": self.engine.system_prompt},
            *history[-MAX_HISTORY:],
        ]

        # Episodic memory：搜索相关历史对话
        try:
            eps = MemoryManager().search_episodes(user_text, top_k=3)
            if eps:
                ctx = "## Relevant Past Experiences\n\n"
                for i, ep in enumerate(eps, 1):
                    ctx += f"{i}. {ep['title']}\n   {ep['summary'][:300]}\n\n"
                messages.insert(1, {"role": "system", "content": ctx})
        except Exception as exc:
            logger.warning("episodic memory injection failed", error=str(exc))

        # Procedural memory：搜索可复用步骤
        try:
            procs = MemoryManager().search_procedures(user_text, top_k=3)
            if procs:
                ctx = "## Relevant Procedures\n\n"
                for i, p in enumerate(procs, 1):
                    ctx += f"{i}. {p['name']}\n   {p['content'][:300]}\n\n"
                messages.insert(1, {"role": "system", "content": ctx})
        except Exception as exc:
            logger.warning("procedural memory injection failed", error=str(exc))

        messages.append({"role": "user", "content": user_text})

        # Working memory compression
        if working_memory_compressible(messages):
            try:
                messages[:] = await compress_working_memory(
                    messages,
                    model=self._model,
                    api_base=self._api_base,
                    api_key=self._api_key,
                )
            except Exception as exc:
                logger.warning("working memory compression failed", error=str(exc))

        try:
            reply = await self.engine.chat(messages)
        except Exception as e:
            logger.exception("LLM call failed")
            reply = f"抱歉，AI 调用失败：{e}"

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        self._histories[chat_id] = history[-MAX_HISTORY:]

        # 自动保存 episodic memory——下次对话可通过 search_episodes 回忆上下文
        try:
            title = user_text.strip()[:48]
            summary = f"User: {user_text[:300]}\nAssistant: {reply[:300]}"
            MemoryManager().save_episode(title=title, summary=summary, tags=[chat_id])
        except Exception as exc:
            logger.warning("episodic memory save failed", error=str(exc))

        return reply
