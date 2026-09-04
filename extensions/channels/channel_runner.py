"""模块说明（中文）：`extensions/channels/channel_runner.py`。

渠道运行器：飞书/企微等渠道的共享 AI 回复逻辑。

提取自 ``scripts/run_feishu_ws.py``，供各渠道独立运行脚本复用。
与 core 完全解耦——只依赖 ConversationEngine + identity，不依赖 FastAPI/PostgreSQL。
"""

from __future__ import annotations

import asyncio
import contextvars
import json as _json
import os
import re
import structlog
import subprocess
import uuid as _uuid
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
_current_chat_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "channel_chat_id", default=""
)
# 思考卡片 message_id——用于 workflow push_feishu 节点覆盖而非发新卡片
_thinking_card_msg_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "channel_thinking_card_msg_id", default=""
)

MAX_HISTORY = 20
MAX_TOOL_ITERATIONS = 30

# ── 公共工具定义 ──────────────────────────────────────────────────────────

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "保存重要信息到持久记忆，下次对话时可自动召回。"
                "发现用户说出偏好、需求、重要背景信息时主动调用。"
                "category: user_profile(用户画像)/project_fact(项目事实)/preference(偏好设置)/reference(参考信息)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "记忆标题（简短关键词）"},
                    "content": {"type": "string", "description": "记忆内容（详细记录，可多行）"},
                    "category": {
                        "type": "string",
                        "description": "类别",
                        "enum": ["user_profile", "project_fact", "preference", "reference"],
                    },
                    "importance": {"type": "number", "description": "重要性 0-1，默认0.7"},
                },
                "required": ["title", "content", "category"],
            },
        },
    },
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
    {
        "type": "function",
        "function": {
            "name": "get_workflow",
            "description": (
                "读取指定工作流的完整定义（含 nodes/edges/config）。"
                "想查 workflow 跑了什么、改之前先看现状、调试节点配置时用这个。"
                "支持 UUID 或 slug（如 'news.tech_weekly'）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow UUID 或 slug"},
                },
                "required": ["workflow_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_workflow",
            "description": (
                "修改已有工作流（仅用户自有副本）。系统预设（is_system=True）不可改——"
                "若要改预设，先调 fork_workflow 拿副本再改。"
                "所有字段可选，未传的字段不动。definition 传完整新定义（不是 patch）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow UUID（必须是用户自有副本）"},
                    "name": {"type": "string", "description": "新名称"},
                    "description": {"type": "string", "description": "新描述"},
                    "definition": {"type": "object", "description": "完整 DAG 定义（覆盖原 definition）"},
                    "is_active": {"type": "boolean", "description": "是否启用"},
                },
                "required": ["workflow_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fork_workflow",
            "description": (
                "把一个工作流（含系统预设）复制成当前用户的可编辑私有副本。"
                "系统预设要个性化必须先 fork 再 update_workflow。"
                "返回新副本的 UUID，slug 为 None（避免与系统 slug 冲突）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "源 workflow UUID 或 slug"},
                    "new_name": {"type": "string", "description": "新副本名称（默认在原名后加 ' (fork)'）"},
                },
                "required": ["workflow_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_workflow",
            "description": (
                "删除指定工作流（仅用户自有副本）。系统预设不可删，会被服务层拒绝。"
                "用于清理废弃的私有副本。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow UUID（必须是用户自有副本）"},
                },
                "required": ["workflow_id"],
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
    if name == "save_memory":
        return await _save_memory(
            args.get("title", ""),
            args.get("content", ""),
            args.get("category", "reference"),
            args.get("importance", 0.7),
        )
    elif name == "run_command":
        return await _run_command(args.get("command", ""))
    elif name == "read_file":
        # read_file 走 io 类别（异步文件读其实是 sync_to_thread，但仍受 io 槽位保护）
        from openagentic.concurrency import get_default_gate
        async with get_default_gate().acquire("io"):
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
    elif name == "get_workflow":
        return await _get_workflow(args.get("workflow_id", ""))
    elif name == "update_workflow":
        return await _update_workflow(
            args.get("workflow_id", ""),
            args.get("name"),
            args.get("description"),
            args.get("definition"),
            args.get("is_active"),
        )
    elif name == "fork_workflow":
        return await _fork_workflow(
            args.get("workflow_id", ""),
            args.get("new_name"),
        )
    elif name == "delete_workflow":
        return await _delete_workflow(args.get("workflow_id", ""))
    return f"未知工具: {name}"


async def _save_memory(title: str, content: str, category: str, importance: float) -> str:
    """保存记忆到 Core Memory（持久化文件存储，下次对话自动召回）。"""
    if not title or not content:
        return "错误：title 和 content 不能为空"
    try:
        from openagentic.memory.manager import MemoryManager
        path = await asyncio.to_thread(
            MemoryManager().save_core_memory,
            key=title,
            value=content,
            category=category,
            importance=float(importance),
        )
        logger.info("memory saved", title=title, category=category, path=path)
        return f"已保存记忆：「{title}」→ {category}"
    except Exception as e:
        logger.exception("save_memory failed")
        return f"保存记忆失败：{e}"


async def _run_command(command: str) -> str:
    cmd = command.strip()
    if not cmd:
        return "错误：命令为空"
    logger.info("[TOOL] run_command", command=cmd[:200])
    # 子进程上限保护：100 用户同时让 bot 跑 git pull 时不击穿机器
    from openagentic.concurrency import get_default_gate
    try:
        async with get_default_gate().acquire("subprocess"):
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
    # 同 _run_command——lark-cli 也是子进程，受同一类别配额保护
    from openagentic.concurrency import get_default_gate
    try:
        async with get_default_gate().acquire("subprocess"):
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
    # 支持 UUID 或 slug 两种方式查找
    try:
        wf_uuid = _uuid.UUID(str(workflow_id))
        lookup_by_slug = False
    except (ValueError, TypeError):
        lookup_by_slug = True
        wf_uuid = None

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        from openagentic.workflow.runtime import runtime
        from sqlalchemy import select
        from openagentic.workflow.models import Workflow
        async with async_session() as db:
            if lookup_by_slug:
                result = await db.execute(
                    select(Workflow).where(Workflow.slug == str(workflow_id))
                )
                workflow = result.scalar_one_or_none()
            else:
                workflow = await wf_service.get_workflow(db, wf_uuid, user_id)
            if not workflow:
                return f"错误：找不到工作流 {workflow_id}（或不属于当前用户）"
            if not workflow.is_active:
                return f"错误：工作流 {workflow.name} 已停用"
            run = await wf_service.create_run(
                db, workflow, input_data or {},
                calling_user_id=user_id,
            )
            run_id = run.id
            wf_id = workflow.id
            wf_name = workflow.name
            await db.commit()

        # sender context 注入：后台任务通过 contextvars 继承当前渠道身份
        platform = _current_platform.get("")
        sender_open_id = _current_sender_open_id.get("")
        chat_id = _current_chat_id.get("")
        # NOTE: 不继承 thinking_card——workflow 始终发新卡片，思考卡留给 agent 文本回复。
        # 历史方案让 workflow 原地替换思考卡，在 ReAct 多轮场景会跟 agent 回复抢同一张卡。
        wf_service._sender_platform.set(platform)
        wf_service._sender_open_id.set(sender_open_id)
        wf_service._channel_chat_id.set(chat_id)
        wf_service._calling_user_id.set(user_id)
        wf_service._thinking_card_msg_id.set("")

        # 后台执行——execute_run_by_id 自带 async_session，不污染当前连接
        runtime.start(run_id, wf_service.execute_run_by_id(run_id, wf_id, user_id,
                                                            calling_user_id=user_id))

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


async def _resolve_workflow(db, lookup: str, user_id):
    """工具内部用：UUID 或 slug 都接受，返回 Workflow 或 None。

    自有 workflow 必须 user_id 匹配；系统预设（is_system=True）所有用户可见。
    """
    import uuid as _uuid
    from sqlalchemy import or_, select
    from openagentic.workflow import service as wf_service
    from openagentic.workflow.models import Workflow

    try:
        wf_uuid = _uuid.UUID(str(lookup))
        return await wf_service.get_workflow(db, wf_uuid, user_id)
    except (ValueError, TypeError):
        # 不是 UUID — 当 slug 处理
        result = await db.execute(
            select(Workflow).where(
                Workflow.slug == str(lookup),
                or_(Workflow.user_id == user_id, Workflow.is_system.is_(True)),
            )
        )
        return result.scalar_one_or_none()


async def _get_workflow(workflow_id: str) -> str:
    """读取工作流完整定义（含 nodes/edges/config），供 agent 改前查看。"""
    import json as _json

    user_id = await _current_user_id()
    if user_id is None:
        return "抱歉，未能识别你的身份，请稍后重试。"
    if not workflow_id:
        return "错误：缺少 workflow_id"

    try:
        from openagentic.db.session import async_session
        async with async_session() as db:
            wf = await _resolve_workflow(db, workflow_id, user_id)
            if not wf:
                return f"错误：找不到工作流 {workflow_id}（或不属于当前用户）"
            payload = {
                "id": str(wf.id),
                "name": wf.name,
                "slug": wf.slug,
                "description": wf.description,
                "definition": wf.definition,
                "version": wf.version,
                "is_active": wf.is_active,
                "is_system": wf.is_system,
            }
        out = _json.dumps(payload, ensure_ascii=False, default=str, indent=2)
        if len(out) > 6000:
            out = out[:6000] + "\n... (definition 截断，可针对具体节点再查)"
        return out
    except Exception as e:
        logger.exception("get_workflow failed")
        return f"读取工作流失败：{e}"


async def _update_workflow(
    workflow_id: str,
    name: str | None,
    description: str | None,
    definition: dict | None,
    is_active: bool | None,
) -> str:
    """更新已有工作流；系统预设走到这里会被 service 拦下，引导调 fork_workflow。"""
    import json as _json

    user_id = await _current_user_id()
    if user_id is None:
        return "抱歉，未能识别你的身份，请稍后重试。"
    if not workflow_id:
        return "错误：缺少 workflow_id"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        from openagentic.workflow.schemas import WorkflowUpdate
        async with async_session() as db:
            wf = await _resolve_workflow(db, workflow_id, user_id)
            if not wf:
                return f"错误：找不到工作流 {workflow_id}（或不属于当前用户）"
            update_kwargs: dict = {}
            if name is not None:
                update_kwargs["name"] = name
            if description is not None:
                update_kwargs["description"] = description
            if definition is not None:
                update_kwargs["definition"] = definition
            if is_active is not None:
                update_kwargs["is_active"] = is_active
            if not update_kwargs:
                return "错误：未提供任何要更新的字段（name/description/definition/is_active 至少一个）"
            body = WorkflowUpdate(**update_kwargs)
            try:
                wf = await wf_service.update_workflow(
                    db, wf, body,
                    is_admin=wf_service.is_admin_user(user_id),
                )
            except wf_service.SystemWorkflowImmutable as e:
                return (
                    f"系统预设不可改：{e}\n"
                    f"先调 fork_workflow('{workflow_id}') 拿副本再 update_workflow。"
                )
            payload = {
                "id": str(wf.id),
                "name": wf.name,
                "version": wf.version,
                "status": "updated",
            }
            await db.commit()
        return _json.dumps(payload, ensure_ascii=False, indent=2)
    except ValueError as e:
        return f"工作流定义校验失败：{e}"
    except Exception as e:
        logger.exception("update_workflow failed")
        return f"更新工作流失败：{e}"


async def _fork_workflow(workflow_id: str, new_name: str | None) -> str:
    """复制工作流到当前用户名下（系统预设变可编辑副本）。"""
    import json as _json

    user_id = await _current_user_id()
    if user_id is None:
        return "抱歉，未能识别你的身份，请稍后重试。"
    if not workflow_id:
        return "错误：缺少 workflow_id"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        async with async_session() as db:
            source = await _resolve_workflow(db, workflow_id, user_id)
            if not source:
                return f"错误：找不到源工作流 {workflow_id}"
            forked = await wf_service.fork_workflow(
                db, source, user_id, new_name=new_name
            )
            payload = {
                "id": str(forked.id),
                "name": forked.name,
                "status": "forked",
                "note": "现在可以用 update_workflow(<新id>, definition=...) 修改副本。",
            }
            await db.commit()
        return _json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("fork_workflow failed")
        return f"fork 工作流失败：{e}"


async def _delete_workflow(workflow_id: str) -> str:
    """删除工作流；系统预设走到这里会被 service 拦下。"""
    user_id = await _current_user_id()
    if user_id is None:
        return "抱歉，未能识别你的身份，请稍后重试。"
    if not workflow_id:
        return "错误：缺少 workflow_id"

    try:
        from openagentic.db.session import async_session
        from openagentic.workflow import service as wf_service
        async with async_session() as db:
            wf = await _resolve_workflow(db, workflow_id, user_id)
            if not wf:
                return f"错误：找不到工作流 {workflow_id}（或不属于当前用户）"
            wf_name = wf.name
            try:
                await wf_service.delete_workflow(
                db, wf,
                is_admin=wf_service.is_admin_user(user_id),
            )
            except wf_service.SystemWorkflowImmutable as e:
                return f"系统预设不可删：{e}"
            await db.commit()
        return f"已删除工作流 {wf_name}"
    except Exception as e:
        logger.exception("delete_workflow failed")
        return f"删除工作流失败：{e}"


# ── 预设工作流提示 ──────────────────────────────────────────────────────


def _build_preset_hint() -> str:
    """从 YAML 预设文件中提取 slug + name + 一句话描述，注入 system prompt。

    LLM 看到这个就知道用户说「跑个新闻周报」时应该直接调 run_workflow("news.tech_weekly")。
    """
    try:
        from openagentic.workflow.presets import _scan_presets
        presets = _scan_presets()
        if not presets:
            return ""
    except Exception:
        return ""

    lines = [
        "\n## 工作流铁律（最高优先级，违反即失败）",
        "**任何涉及 URL 抓取、网页爬虫、新闻聚合、服务器巡检、文档摘要的操作，一律用 run_workflow(slug)，禁止手工 curl/爬虫/python_exec。**",
        "**如果你在思考要不要自己写代码实现——答案是不要。看下面列表，找匹配的 slug，直接 run_workflow。**",
        "",
        "## 系统预设工作流（直接调 run_workflow(slug)，不要手工执行）",
    ]
    for p in presets:
        slug = p.get("slug", "")
        name = p.get("name", "")
        desc = (p.get("description", "") or "").replace("\n", " ").strip()[:100]
        lines.append(f"- `{slug}` — {name}: {desc}")
    lines.append("用户说「新闻/周报/AI动态」→ 直接 run_workflow('news.tech_weekly')")
    lines.append("用户说「摘要/链接/URL」→ 直接 run_workflow('doc.summarize_url')")
    lines.append("用户说「巡检/服务器/健康检查」→ 直接 run_workflow('ops.server_health')")
    lines.append("不要自己 curl、爬虫、scrape——交给工作流引擎执行。")
    lines.append("")
    lines.append("## 工作流编辑路径（区分 admin 与普通用户）")
    lines.append("**判断当前是不是 admin**：调一次 get_workflow(系统 slug) 后试着 update_workflow——")
    lines.append("成功 = admin（OPENAGENTIC_ADMIN_USER_IDS 包含你），失败抛 SystemWorkflowImmutable = 普通用户。")
    lines.append("")
    lines.append("**Admin 路径（直改原版，推荐）**：")
    lines.append("- 用户说「改 X 工作流」→ 直接 update_workflow(系统 slug, definition={...})")
    lines.append("- **不要 fork**，直接改原版；改动持久（除非 yaml 里升 version 触发 lifespan 覆盖）")
    lines.append("- 若历史上误 fork 过多个副本（is_system=False, slug=None 跟系统预设同主题）→ list_workflows 找出来，逐一调 delete_workflow 清理")
    lines.append("")
    lines.append("**普通用户路径（fork 后改副本）**：")
    lines.append("- update_workflow 系统 slug 报 SystemWorkflowImmutable → 自动回退：先 fork_workflow，再 update_workflow(<新id>, ...)")
    lines.append("- 跑工作流时优先 list_workflows 找自己 forked 副本（is_system=False, name 与原预设主题相关），优先跑副本")
    lines.append("")
    lines.append("## 工作流自管理（你能改任何 workflow）")
    lines.append("- **改前必读**：先调 get_workflow(id_or_slug) 读完整 definition，不要凭印象改")
    lines.append("- **系统预设只读**：is_system=True 的 workflow 改不动；用户要个性化时先 fork_workflow(slug, new_name?) 拿副本，再 update_workflow(<新id>, definition={...})")
    lines.append("- **失败诊断**：run 失败时调 query_workflow_run(run_id) 看 trace 里 status=failed 节点的 error 字段，把错误原文回复用户，不要去 find/grep 探索文件系统")
    lines.append("- **definition 是完整覆盖**：update_workflow 的 definition 是整体替换，不是 patch；先 get_workflow 拿全量再改某个 node")
    return "\n".join(lines)


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

        # 注入可用系统预设工作流（LLM 看到后直接调 run_workflow，不会手工爬）
        preset_hint = _build_preset_hint()
        if preset_hint:
            system_prompt += "\n" + preset_hint

        # 飞书/企微回复格式限制
        system_prompt += (
            "\n\n## 回复格式限制（飞书 lark_md 不支持的语法）"
            "\n- 禁止表格（|...| 格式）、围栏代码块（```）、Markdown 标题（#）"
            "\n- 用加粗、列表、缩进代替"
            "\n- 代码片段用缩进 4 空格展示"
            "\n- 用户发「表格/代码块」时可忽略此限制（用户显式要求时允许）"
        )

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

        通过 ConcurrencyGate 接入并发底座：
        - session_key=chat_id：同会话严格串行，杜绝 _histories 竞态
        - category="default"：业务级配额；底层 LLM/子进程调用各自走自己类别
        - timeout 不在此设置，由底座默认值或上层 wait_for 兜底（飞书层已 180s）

        每轮自动注入 episodic + procedural memory，触发 working memory 压缩。
        platform/sender_open_id 用于在工具执行（如 run_workflow）时按 user_channel_bindings 解析归属用户。
        """
        from openagentic.concurrency import get_default_gate, GateBusy, GateTimeout

        # 把渠道身份塞到 contextvars，供本次 LLM 调用链内的工具读取——
        # 必须在 submit 外层 set，因为 contextvars 在 submit 内层 await 也能读到（继承自当前 task）。
        _platform_token = _current_platform.set(platform)
        _sender_token = _current_sender_open_id.set(sender_open_id)
        _chat_token = _current_chat_id.set(chat_id)
        try:
            # ── 快路径：匹配已知命令，绕过 LLM 直接执行 ──
            fast_reply = await self._fast_path_reply(user_text, chat_id)
            if fast_reply is not None:
                return fast_reply

            try:
                return await get_default_gate().submit(
                    session_key=chat_id,
                    coro_factory=lambda: self._reply_inner(user_text, chat_id),
                )
            except GateBusy:
                logger.warning("gate busy, dropping reply", chat_id=chat_id)
                return "服务繁忙，请稍后重试。"
            except GateTimeout:
                logger.warning("gate timeout", chat_id=chat_id)
                return "处理超时，请稍后重试。"
        finally:
            _current_platform.reset(_platform_token)
            _current_sender_open_id.reset(_sender_token)
            _current_chat_id.reset(_chat_token)

    # ── 快路径匹配 ──────────────────────────────────────────────────────
    _FAST_RUN_RE = re.compile(r"^[/]?(run|启动|运行)\s+(\S+)", re.IGNORECASE)
    _FAST_QUERY_RE = re.compile(
        r"^[/]?(query|查询|状态)\S*\s+([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})",
        re.IGNORECASE,
    )
    # query_workflow_run 不带参数 = 查最近一次运行状态
    _FAST_QUERY_BARE_RE = re.compile(r"^[/]?(query|状态|status)\S*$", re.IGNORECASE)
    _FAST_LIST_RE = re.compile(r"^[/]?(list|ls|列表|列出)", re.IGNORECASE)

    async def _fast_path_reply(self, user_text: str, chat_id: str) -> str | None:
        """匹配已知命令模式，直接执行不经过 LLM。返回 None 表示未命中。"""
        text = user_text.strip()

        # /list 或 "列表"
        if self._FAST_LIST_RE.match(text):
            logger.info("fast_path: list", text=text[:50])
            return await _list_workflows()

        # query_workflow_run / status / 状态（无参） → 最近一次运行
        if self._FAST_QUERY_BARE_RE.match(text):
            logger.info("fast_path: status", text=text[:50])
            return await self._fast_last_run_status(chat_id)

        # /query <run_id> / 查询 <run_id>
        m = self._FAST_QUERY_RE.match(text)
        if m:
            run_id = m.group(2)
            logger.info("fast_path: query", run_id=run_id[:8])
            return await _query_workflow_run(run_id)

        # /run <slug> 或 /run <name>
        m = self._FAST_RUN_RE.match(text)
        if m:
            slug_or_name = m.group(2)
            logger.info("fast_path: run", slug=slug_or_name[:50])
            return await self._fast_run_by_slug(slug_or_name)

        logger.debug("fast_path: miss, falling through to LLM", text=text[:100])
        return None

    async def _fast_run_by_slug(self, slug_or_name: str) -> str:
        """按 slug 或名称查找预设/用户工作流，直接启动。"""
        user_id = await _current_user_id()
        if user_id is None:
            return "抱歉，未能识别你的身份。"

        try:
            from openagentic.db.session import async_session
            from openagentic.workflow import service as wf_service
            from openagentic.workflow.runtime import runtime
            from sqlalchemy import or_, select
            from openagentic.workflow.models import Workflow

            async with async_session() as db:
                result = await db.execute(
                    select(Workflow).where(
                        Workflow.is_active == True,  # noqa: E712
                        or_(
                            Workflow.slug == slug_or_name,
                            Workflow.name == slug_or_name,
                        ),
                    )
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    return f"未找到工作流「{slug_or_name}」。输入「list」查看可用列表。"

                # 检查权限：用户自有或系统工作流
                if not wf.is_system and wf.user_id != user_id:
                    return f"工作流「{wf.name}」不属于你。"

                run = await wf_service.create_run(db, wf, {},
                                                  calling_user_id=user_id)
                run_id = run.id
                wf_id = wf.id
                wf_name = wf.name
                await db.commit()

            platform = _current_platform.get("")
            sender_open_id = _current_sender_open_id.get("")
            chat_id = _current_chat_id.get("")
            from openagentic.workflow import service as wf_service2
            wf_service2._sender_platform.set(platform)
            wf_service2._sender_open_id.set(sender_open_id)
            wf_service2._channel_chat_id.set(chat_id)
            wf_service2._calling_user_id.set(user_id)
            # 同上：workflow 不继承思考卡片，永远发新卡片。
            wf_service2._thinking_card_msg_id.set("")

            runtime.start(
                run_id,
                wf_service2.execute_run_by_id(run_id, wf_id, user_id,
                                              calling_user_id=user_id),
            )

            return _json.dumps({
                "run_id": str(run_id),
                "workflow": wf_name,
                "status": "started",
                "note": "已在后台启动，用「query <run_id>」查进度。",
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception("fast_run_by_slug failed")
            return f"启动失败：{e}"

    async def _fast_last_run_status(self, chat_id: str) -> str:
        """查询当前会话最近一次 workflow run 的状态。"""
        user_id = await _current_user_id()
        if user_id is None:
            return "抱歉，未能识别你的身份。"
        try:
            from openagentic.db.session import async_session
            from openagentic.workflow import service as wf_service
            async with async_session() as db:
                runs = await wf_service.list_runs(db, user_id)
            if not runs:
                return "没有找到运行记录。"
            latest = runs[0]
            status = latest.status.value if hasattr(latest.status, "value") else str(latest.status)
            return f"最近运行: {latest.id}\n状态: {status}\n结果: {(latest.output_data or {}).get('result', '(无)')}"
        except Exception as e:
            logger.exception("fast_last_run_status failed")
            return f"查询失败：{e}"

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

        # Episodic / Procedural memory：原 MemoryManager 是同步文件 I/O，
        # 直接 await 会阻塞 event loop 拖慢所有其他用户；用 to_thread 隔离到线程池。
        try:
            eps = await asyncio.to_thread(
                MemoryManager().search_episodes, user_text, 3
            )
            if eps:
                ctx = "## Relevant Past Experiences\n\n"
                for i, ep in enumerate(eps, 1):
                    ctx += f"{i}. {ep['title']}\n   {ep['summary'][:300]}\n\n"
                messages[0]["content"] += "\n\n" + ctx  # 合并进主 system(位置0): 严格 system-first 模型(Qwen3.8)拒绝位置1的system
        except Exception as exc:
            logger.warning("episodic memory injection failed", error=str(exc))

        try:
            procs = await asyncio.to_thread(
                MemoryManager().search_procedures, user_text, 3
            )
            if procs:
                ctx = "## Relevant Procedures\n\n"
                for i, p in enumerate(procs, 1):
                    ctx += f"{i}. {p['name']}\n   {p['content'][:300]}\n\n"
                messages[0]["content"] += "\n\n" + ctx  # 合并进主 system(位置0): 严格 system-first 模型(Qwen3.8)拒绝位置1的system
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
            await asyncio.to_thread(
                MemoryManager().save_episode, title, summary, [chat_id]
            )
        except Exception as exc:
            logger.warning("episodic memory save failed", error=str(exc))

        return reply
