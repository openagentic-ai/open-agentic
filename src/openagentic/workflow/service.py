"""模块说明（中文）：`src/openagentic/workflow/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

from __future__ import annotations

import asyncio
import contextvars
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent.tools import default_registry
from openagentic.core.llm.service import chat_completion
from openagentic.core.llm.provider_config import get_provider_store
from openagentic.db.session import async_session
from openagentic.workflow.models import TERMINAL_STATUSES, ExecutionStatus, Workflow, WorkflowExecution
from openagentic.workflow.schemas import WorkflowCreate, WorkflowUpdate

# ── Sender context（渠道触发的工作流节点执行时读取） ────────────────────
# HTTP 路由在执行前设置 _calling_user_id；渠道 runner 额外设置 _sender_platform / _sender_open_id。
# _execute_node 在执行 feishu/wecom 节点时读取这些值，注入子进程环境变量。
_sender_platform: contextvars.ContextVar[str] = contextvars.ContextVar(
    "wf_sender_platform", default=""
)
_sender_open_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "wf_sender_open_id", default=""
)
_channel_chat_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "wf_channel_chat_id", default=""
)
_calling_user_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "wf_calling_user_id", default=None
)
_thinking_card_msg_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "wf_thinking_card_msg_id", default=""
)

logger = structlog.get_logger("openagentic.workflow.service")

VAR_PATTERN = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
TRACE_KEY = "trace"
CANCEL_KEY = "_cancel_requested"
# Phase 7 Sub-milestone 1.1：节点级挂起信号槽。
# approval / human_input 节点声明 _waiting_for: {type, instance_key, node_id, ...} 写入 node_states，
# runtime 把 run 状态置为 suspended 并 break。事件触发器（飞书/企微 webhook）按 instance_key 反查 → resume。
WAITING_FOR_KEY = "_waiting_for"
# resume 时由唤醒接口写入的载荷（例如 {"approved": true} / {"text": "用户输入"}），
# runtime 在节点边界消费后 pop。
RESUME_PAYLOAD_KEY = "_resume_payload"
# Phase 7 Sub-milestone 1.2：挂起状态持久化键。
# _execute_definition 在节点请求挂起时将已完成的 outputs 写入此键，resume 时从该键恢复。
OUTPUTS_CACHE_KEY = "_outputs"
# _execute_node 返回的挂起信号标志。
SUSPEND_FLAG = "__suspend__"

# 条件边表达式解析：{{nodes.x}} == "value" / {{nodes.x}} != "value" / {{nodes.x}}
_COND_EQ_RE = re.compile(r"^\{\{\s*([^}]+)\s*\}\}\s*==\s*[\"']([^\"']*)[\"']$")
_COND_NE_RE = re.compile(r"^\{\{\s*([^}]+)\s*\}\}\s*!=\s*[\"']([^\"']*)[\"']$")
_COND_TRUTHY_RE = re.compile(r"^\{\{\s*([^}]+)\s*\}\}$")


async def list_workflows(db: AsyncSession, user_id: uuid.UUID) -> list[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(or_(Workflow.user_id == user_id, Workflow.is_system == True))  # noqa: E712
        .order_by(Workflow.is_system.desc(), Workflow.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            or_(Workflow.user_id == user_id, Workflow.is_system == True),  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


def _validate_node_config(node_id: str, node_type: str, config: dict[str, Any]) -> None:
    """节点级 config 必填校验——在 create_workflow 阶段就拦截，避免运行时秒挂。

    历史教训：LLM 调 create_workflow 时常漏写 tool_name/prompt/subcommand，
    工作流创建成功但执行时 1 秒内 failed，bot 却仍然回复"已启动 ✅"。
    把校验前移到创建期，让错误在调用 create_workflow 时就抛出。
    """
    if not isinstance(config, dict):
        raise ValueError(f"Node '{node_id}' config must be an object")

    if node_type == "tool":
        tool_name = config.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            known = ", ".join(default_registry.list_tool_names())
            raise ValueError(
                f"Node '{node_id}' (type=tool) requires config.tool_name. "
                f"Known tools: {known}"
            )
        known_names = default_registry.list_tool_names()
        if tool_name not in known_names:
            raise ValueError(
                f"Node '{node_id}' (type=tool) references unknown tool '{tool_name}'. "
                f"Known tools: {', '.join(known_names)}"
            )
    elif node_type == "llm":
        prompt = config.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Node '{node_id}' (type=llm) requires config.prompt")
    elif node_type in ("feishu", "wecom"):
        subcommand = config.get("subcommand")
        # 飞书 card 模式可不需要 subcommand，但需要 chat_id + content
        if node_type == "feishu" and config.get("format") == "card":
            if not config.get("chat_id"):
                raise ValueError(f"Node '{node_id}' (feishu card) requires config.chat_id")
            if not config.get("content"):
                raise ValueError(f"Node '{node_id}' (feishu card) requires config.content")
        elif not isinstance(subcommand, str) or not subcommand.strip():
            raise ValueError(f"Node '{node_id}' (type={node_type}) requires config.subcommand")
    elif node_type == "evaluator":
        if not config.get("target_node"):
            raise ValueError(f"Node '{node_id}' (type=evaluator) requires config.target_node")
        if not config.get("criteria"):
            raise ValueError(f"Node '{node_id}' (type=evaluator) requires config.criteria")
    elif node_type == "value":
        if "value" not in config:
            raise ValueError(f"Node '{node_id}' (type=value) requires config.value")
    # approval / human_input：执行期由挂起信号定义具体配置，此处不强校验


def validate_definition(definition: dict[str, Any]) -> None:
    """校验工作流定义是否合法。

    重点检查：
    - nodes/edges 结构；
    - 节点 ID 唯一性；
    - 节点类型是否支持；
    - 节点 config 必填字段（tool_name / prompt / subcommand 等）；
    - edge 引用是否存在；
    - 图是否有环（通过拓扑排序检测）。
    """
    nodes = definition.get("nodes")
    edges = definition.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("definition.nodes must be a non-empty array")
    if not isinstance(edges, list):
        raise ValueError("definition.edges must be an array")

    node_ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Each node must be an object")
        node_id = node.get("id")
        node_type = node.get("type")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("Each node must contain a non-empty id")
        if node_id in node_ids:
            raise ValueError(f"Duplicate node id: {node_id}")
        if node_type not in {"value", "tool", "llm", "approval", "human_input", "feishu", "wecom", "evaluator"}:
            raise ValueError(f"Unsupported node type: {node_type}")
        # 创建期就拦下缺 config 的节点，避免运行时秒挂导致用户被骗"已启动"。
        _validate_node_config(node_id, node_type, node.get("config") or {})
        node_ids.append(node_id)

    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Each edge must be an object")
        src = edge.get("from")
        dst = edge.get("to")
        if src not in node_ids or dst not in node_ids:
            raise ValueError(f"Edge references unknown node: {src} -> {dst}")

    _topological_order(definition)


async def create_workflow(db: AsyncSession, user_id: uuid.UUID, body: WorkflowCreate) -> Workflow:
    """创建工作流前先做定义校验。"""
    validate_definition(body.definition)
    workflow = Workflow(
        user_id=user_id,
        name=body.name,
        slug=body.slug or None,
        description=body.description,
        definition=body.definition,
        is_active=True,
        is_system=False,
    )
    db.add(workflow)
    await db.flush()
    return workflow


def is_admin_user(user_id: uuid.UUID | None) -> bool:
    """env OPENAGENTIC_ADMIN_USER_IDS 包含该 user_id 即视为 admin。

    admin 可绕过 SystemWorkflowImmutable 直接改系统预设——单租户/部署管理员场景。
    多租户/普通员工不在该列表，仍按 fork 流程走。
    """
    if user_id is None:
        return False
    raw = os.getenv("OPENAGENTIC_ADMIN_USER_IDS", "").strip()
    if not raw:
        return False
    target = str(user_id)
    return any(part.strip() == target for part in raw.split(","))


class SystemWorkflowImmutable(ValueError):
    """系统预设工作流不可改/删——抛出此异常让路由层映射为 400/403，引导用户 fork。"""


async def update_workflow(
    db: AsyncSession,
    workflow: Workflow,
    body: WorkflowUpdate,
    *,
    is_admin: bool = False,
) -> Workflow:
    """更新工作流；若 definition 被修改，会再次校验。

    系统预设（is_system=True）由 presets/*.yaml 单一事实源管理，普通用户需 fork；
    is_admin=True 时（OPENAGENTIC_ADMIN_USER_IDS 包含的 user_id）允许直接改系统预设原版。
    """
    if workflow.is_system and not is_admin:
        raise SystemWorkflowImmutable(
            "System preset workflows are immutable. Fork it via POST /api/workflows/{id}/fork to customize."
        )
    patch = body.model_dump(exclude_unset=True)
    if "definition" in patch and patch["definition"] is not None:
        validate_definition(patch["definition"])
    for field, value in patch.items():
        setattr(workflow, field, value)
    await db.flush()
    return workflow


async def delete_workflow(
    db: AsyncSession,
    workflow: Workflow,
    *,
    is_admin: bool = False,
) -> None:
    """删除工作流；系统预设默认禁止删除，is_admin=True 时放行。"""
    if workflow.is_system and not is_admin:
        raise SystemWorkflowImmutable(
            "System preset workflows cannot be deleted; remove the YAML in presets/ if you really mean to."
        )
    await db.delete(workflow)


async def fork_workflow(
    db: AsyncSession, source: Workflow, user_id: uuid.UUID, new_name: str | None = None
) -> Workflow:
    """复制一份工作流到当前用户名下（用于把系统预设变成可编辑的私有副本）。

    新副本：user_id=current, is_system=False, slug=None（避免与系统 slug 冲突）, version=1。
    """
    workflow = Workflow(
        user_id=user_id,
        name=new_name or f"{source.name} (fork)",
        slug=None,
        description=source.description,
        definition=source.definition,
        is_active=True,
        is_system=False,
    )
    db.add(workflow)
    await db.flush()
    return workflow


async def create_run(
    db: AsyncSession,
    workflow: Workflow,
    input_data: dict[str, Any] | None,
    calling_user_id: uuid.UUID | None = None,
) -> WorkflowExecution:
    """创建一次运行记录（初始状态 pending）。

    系统工作流的 run 归属调用者（calling_user_id），而非 workflow 所有者；
    用户自有工作流保持原有语义（run 归属 = workflow 所有者）。
    """
    owner_id = calling_user_id if workflow.is_system and calling_user_id else workflow.user_id
    run = WorkflowExecution(
        workflow_id=workflow.id,
        user_id=owner_id,
        status=ExecutionStatus.pending,
        input_data=input_data or {},
        output_data=None,
        node_states={TRACE_KEY: []},
    )
    db.add(run)
    await db.flush()
    return run


async def list_runs(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID | None = None
) -> list[WorkflowExecution]:
    stmt = select(WorkflowExecution).where(WorkflowExecution.user_id == user_id).order_by(
        WorkflowExecution.created_at.desc()
    )
    if workflow_id:
        stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_run(
    db: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID
) -> WorkflowExecution | None:
    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == run_id,
            WorkflowExecution.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def request_cancel(db: AsyncSession, run: WorkflowExecution) -> WorkflowExecution:
    """标记取消请求（软取消标记，执行循环会主动感知）。"""
    run.node_states = {**(run.node_states or {}), CANCEL_KEY: True}
    await db.flush()
    return run


def _is_cancel_requested(run: WorkflowExecution) -> bool:
    """统一判断 run 是否已被请求取消。"""
    node_states = getattr(run, "node_states", None) or {}
    if bool(node_states.get(CANCEL_KEY)):
        return True
    return bool(getattr(run, "cancel_requested", False))


def get_waiting_for(run: WorkflowExecution) -> dict[str, Any] | None:
    """读取节点挂起信号槽。runtime 在节点边界检查；触发器按 instance_key 反查命中的 run。

    返回示例：{"type": "feishu_approval", "instance_key": "RECxxxx", "node_id": "approve"}
    若未挂起返回 None。
    """
    node_states = getattr(run, "node_states", None) or {}
    waiting = node_states.get(WAITING_FOR_KEY)
    return waiting if isinstance(waiting, dict) else None


def set_waiting_for(run: WorkflowExecution, signal: dict[str, Any]) -> None:
    """设置节点挂起信号槽。需要包含至少 type/instance_key/node_id。

    调用方负责 await db.flush()。
    """
    if not isinstance(signal, dict):
        raise TypeError("waiting_for signal must be a dict")
    required = {"type", "instance_key", "node_id"}
    missing = required - set(signal.keys())
    if missing:
        raise ValueError(f"waiting_for signal missing keys: {sorted(missing)}")
    run.node_states = {**(run.node_states or {}), WAITING_FOR_KEY: signal}


def clear_waiting_for(run: WorkflowExecution) -> dict[str, Any] | None:
    """清除节点挂起信号槽并返回原值（用于 resume 时取出元数据）。"""
    node_states = dict(run.node_states or {})
    waiting = node_states.pop(WAITING_FOR_KEY, None)
    run.node_states = node_states
    return waiting if isinstance(waiting, dict) else None


def set_resume_payload(run: WorkflowExecution, payload: dict[str, Any]) -> None:
    """resume 接口写入唤醒载荷，runtime 在节点边界消费后 pop。"""
    if not isinstance(payload, dict):
        raise TypeError("resume payload must be a dict")
    run.node_states = {**(run.node_states or {}), RESUME_PAYLOAD_KEY: payload}


def pop_resume_payload(run: WorkflowExecution) -> dict[str, Any] | None:
    """读取并移除 resume 载荷。runtime 唤醒后调用。"""
    node_states = dict(run.node_states or {})
    payload = node_states.pop(RESUME_PAYLOAD_KEY, None)
    run.node_states = node_states
    return payload if isinstance(payload, dict) else None


async def execute_run(
    db: AsyncSession, run: WorkflowExecution, workflow: Workflow,
    resume: bool = False,
) -> WorkflowExecution:
    """执行单次 Run。

    状态流转：
    pending -> running -> completed/failed/cancelled
    中途可进入 suspended（approval/human_input 节点触发），
    resume 时从 suspended 回到 running。

    当 resume=True 时：从 node_states 恢复已缓存的 outputs/trace，
    消费 resume payload 作为挂起节点的输出，清除 waiting_for 后继续拓扑序。
    """
    t0 = time.monotonic()

    if not resume:
        # 全新执行：重置状态
        run.status = ExecutionStatus.running
        run.started_at = datetime.now(timezone.utc)
        run.completed_at = None
        run.output_data = None
        run.node_states = {TRACE_KEY: []}
        initial_outputs = None
        initial_trace = None
    else:
        # Resume 执行：从缓存恢复
        node_states = dict(run.node_states or {})
        initial_outputs = node_states.pop(OUTPUTS_CACHE_KEY, None) or {}
        initial_trace = node_states.pop(TRACE_KEY, None) or []

        # 消费 resume payload 作为挂起节点的输出
        resume_data = pop_resume_payload(run)
        waiting_for = clear_waiting_for(run)
        if waiting_for:
            suspended_node_id = waiting_for.get("node_id")
            if suspended_node_id and resume_data is not None:
                initial_outputs[suspended_node_id] = resume_data

        run.status = ExecutionStatus.running
        run.completed_at = None
        await db.flush()

    logger.info("execute_run start", run_id=str(getattr(run, "id", "")),
                workflow_slug=getattr(workflow, "slug", ""),
                workflow_name=getattr(workflow, "name", ""),
                status=run.status.value, resume=resume)

    try:
        output, trace = await _execute_definition(
            db=db,
            run=run,
            definition=workflow.definition,
            input_payload=run.input_data or {},
            initial_outputs=initial_outputs,
            initial_trace=initial_trace,
        )
        if _is_cancel_requested(run):
            run.status = ExecutionStatus.cancelled
        elif run.status == ExecutionStatus.suspended:
            # _execute_definition 已将 run 置为 suspended 并持久化了 outputs/trace
            logger.info("execute_run suspended", run_id=str(getattr(run, "id", "")),
                        waiting_for=get_waiting_for(run))
        else:
            run.status = ExecutionStatus.completed
        if run.status != ExecutionStatus.suspended:
            run.output_data = {"result": output}
            run.node_states = {**(run.node_states or {}), TRACE_KEY: trace}
    except asyncio.CancelledError:
        # 外部协程取消（如任务终止）统一映射为 cancelled。
        run.status = ExecutionStatus.cancelled
        run.node_states = {**(run.node_states or {}), "error": "Run cancelled"}
        logger.info("execute_run cancelled", run_id=str(getattr(run, "id", "")))
    except Exception as exc:
        run.status = ExecutionStatus.failed
        run.node_states = {**(run.node_states or {}), "error": str(exc)}
        logger.error("execute_run failed", run_id=str(getattr(run, "id", "")), error=str(exc),
                     exc_info=True)
    finally:
        if run.status in TERMINAL_STATUSES:
            run.completed_at = datetime.now(timezone.utc)
        elapsed = time.monotonic() - t0
        logger.info("execute_run done", run_id=str(getattr(run, "id", "")), status=run.status.value,
                    elapsed_ms=round(elapsed * 1000))
        await db.flush()
    return run


async def execute_run_by_id(
    run_id: uuid.UUID, workflow_id: uuid.UUID, user_id: uuid.UUID,
    calling_user_id: uuid.UUID | None = None,
) -> None:
    """后台任务入口：按 ID 拉取 run/workflow 并执行。"""
    async with async_session() as db:
        run = await get_run(db, run_id, user_id)
        workflow = await get_workflow(db, workflow_id, user_id)
        if not run or not workflow:
            return
        await execute_run(db, run, workflow)
        await db.commit()


def _topological_order(definition: dict[str, Any]) -> list[str]:
    """返回 DAG 拓扑序；若有环则抛 ValueError。"""
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])
    ids = [n["id"] for n in nodes]
    indeg = {node_id: 0 for node_id in ids}
    graph: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in edges:
        src = edge["from"]
        dst = edge["to"]
        graph[src].append(dst)
        indeg[dst] += 1

    queue = [n for n in ids if indeg[n] == 0]
    order: list[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for nxt in graph[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(ids):
        raise ValueError("Workflow definition contains cycle")
    return order


async def _execute_definition(
    db: AsyncSession,
    run: WorkflowExecution,
    definition: dict[str, Any],
    input_payload: dict[str, Any],
    initial_outputs: dict[str, Any] | None = None,
    initial_trace: list[dict[str, Any]] | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """按拓扑序执行整个定义并生成 trace。

    resume 场景：传入 initial_outputs/initial_trace，已在 outputs 中的 node_id 直接跳过——
    挂起前已完成的节点 + 唤醒注入的节点输出 都按缓存值供下游引用。
    """
    nodes = {n["id"]: n for n in definition.get("nodes", [])}
    order = _topological_order(definition)
    outputs: dict[str, Any] = dict(initial_outputs or {})
    trace: list[dict[str, Any]] = list(initial_trace or [])

    for node_id in order:
        # resume 场景：节点已执行过（或被 resume 注入），跳过
        if node_id in outputs:
            continue

        await db.refresh(run)
        if _is_cancel_requested(run):
            trace.append({"node_id": node_id, "status": "cancelled", "reason": "cancel_requested"})
            break

        node = nodes[node_id]
        node_type_name = node.get("type", "")

        run_id_str = str(getattr(run, "id", ""))
        logger.debug("execute node start", run_id=run_id_str, node_id=node_id,
                     node_type=node_type_name)

        # 条件边检查：入边条件全部为 False 时跳过此节点
        should_skip, skip_reason = _should_skip_node(node_id, definition, outputs)
        if should_skip:
            logger.debug("execute node skipped", run_id=str(getattr(run, "id", "")), node_id=node_id,
                         reason=skip_reason)
            trace.append({
                "node_id": node_id,
                "node_type": node_type_name,
                "status": "skipped",
                "reason": skip_reason,
            })
            continue

        # 构建 context 维度（渠道 sender 身份），供 {{context.xxx}} 引用
        render_context: dict[str, Any] = {"input": input_payload, "nodes": outputs}
        sender_platform = _sender_platform.get("")
        sender_open_id = _sender_open_id.get("")
        chat_id = _channel_chat_id.get("")
        calling_uid = _calling_user_id.get()
        ctx: dict[str, str] = {}
        if sender_platform:
            ctx["sender_platform"] = sender_platform
        if sender_open_id:
            ctx["sender_open_id"] = sender_open_id
        if chat_id:
            ctx["chat_id"] = chat_id
        if calling_uid:
            ctx["calling_user_id"] = str(calling_uid)
        if ctx:
            render_context["context"] = ctx

        rendered = _render_value(node.get("config", {}), render_context)

        # evaluator 预处理：解析 target_node，注入其输出作为 target_output
        if node_type_name == "evaluator":
            target_node_id = rendered.get("target_node")
            if target_node_id and target_node_id in outputs:
                rendered["target_output"] = outputs[target_node_id]

        retries = int(rendered.get("retries", 0) or 0)
        timeout_sec = float(rendered.get("timeout_sec", 60) or 60)
        attempts = 0
        last_err: str | None = None

        while attempts <= retries:
            attempts += 1
            try:
                output = await asyncio.wait_for(
                    _execute_node(node_type=node["type"], config=rendered),
                    timeout=timeout_sec,
                )
                # Phase 7 1.2：approval / human_input 节点返回挂起信号
                if isinstance(output, dict) and output.pop(SUSPEND_FLAG, None):
                    signal = {
                        "type": output.pop("suspend_type", f"{node['type']}_suspend"),
                        "instance_key": output.pop("instance_key", ""),
                        "node_id": node_id,
                    }
                    signal.update(output)  # 携带其余元数据（channel/prompt 等）
                    set_waiting_for(run, signal)
                    trace.append({
                        "node_id": node_id,
                        "node_type": node_type_name,
                        "status": "suspended",
                        "waiting_for": signal,
                    })
                    logger.info("execute node suspended", run_id=str(getattr(run, "id", "")),
                                node_id=node_id, signal_type=signal.get("type"))
                    # 持久化已完成的 outputs + trace 供 resume 恢复
                    run.node_states = {
                        **(run.node_states or {}),
                        TRACE_KEY: trace,
                        OUTPUTS_CACHE_KEY: outputs,
                    }
                    run.status = ExecutionStatus.suspended
                    await db.flush()
                    return None, trace

                outputs[node_id] = output

                # evaluator 后处理：passed=false 时触发目标节点重试
                is_evaluator = node_type_name == "evaluator"
                eval_passed = is_evaluator and isinstance(output, dict) and output.get("passed")
                eval_retries_left = 0
                if is_evaluator and isinstance(output, dict) and not output.get("passed"):
                    eval_max_retries = int(rendered.get("max_retries", 2) or 2)
                    eval_retries_used = int(rendered.get("_eval_retries_used", 0) or 0)
                    eval_retries_left = eval_max_retries - eval_retries_used
                    if eval_retries_left > 0 and target_node_id and target_node_id in nodes:
                        # 重新执行 target_node
                        target = nodes[target_node_id]
                        target_rendered = _render_value(target.get("config", {}), render_context)
                        logger.info("evaluator retrying target", node_id=node_id,
                                    target_node=target_node_id, retries_left=eval_retries_left)
                        try:
                            target_output = await asyncio.wait_for(
                                _execute_node(node_type=target["type"], config=target_rendered),
                                timeout=float(target_rendered.get("timeout_sec", 60) or 60),
                            )
                            outputs[target_node_id] = target_output
                            # 更新 rendered 中的 target_output 并重试 evaluator
                            rendered["target_output"] = target_output
                            rendered["_eval_retries_used"] = eval_retries_used + 1
                            # 回到 while 循环重试 evaluator
                            del outputs[node_id]  # 清除本次 evaluator 结果
                            attempts = 0  # 重置重试计数
                            continue
                        except Exception as target_exc:
                            logger.error("evaluator target retry failed", target_node=target_node_id,
                                        error=str(target_exc))
                            break

                trace.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type_name,
                        "status": "success",
                        "attempt": attempts,
                        "output": output,
                    }
                )
                logger.info("execute node success", run_id=str(getattr(run, "id", "")),
                            node_id=node_id, node_type=node_type_name, attempt=attempts)
                break
            except Exception as exc:  # noqa: PERF203
                # 失败后根据 retries 决定重试或失败终止，并记录结构化 trace。
                last_err = str(exc)
                if attempts > retries:
                    trace.append(
                        {
                            "node_id": node_id,
                            "node_type": node_type_name,
                            "status": "failed",
                            "attempt": attempts,
                            "error": last_err,
                        }
                    )
                    logger.error("execute node failed", run_id=str(getattr(run, "id", "")),
                                 node_id=node_id, node_type=node_type_name,
                                 attempt=attempts, error=last_err)
                    raise RuntimeError(f"Node {node_id} failed: {last_err}") from exc
                trace.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type_name,
                        "status": "retrying",
                        "attempt": attempts,
                        "error": last_err,
                    }
                )
                logger.warning("execute node retrying", run_id=str(getattr(run, "id", "")),
                               node_id=node_id, node_type=node_type_name,
                               attempt=attempts, error=last_err)

    final_output = outputs[order[-1]] if order and order[-1] in outputs else None
    return final_output, trace


async def _run_cli(
    binary: str, subcommand: str, args: list, platform: str = ""
) -> dict[str, Any]:
    """执行 CLI 二进制，返回 {stdout, stderr, returncode}。

    若 sender context 中有渠道身份，注入子进程环境变量
    供 lark-cli/wecom-cli 使用发送者凭据而非 bot 默认凭据。
    """
    cmd = [binary] + subcommand.split() + [str(a) for a in args]
    extra_env = {}
    sender_platform = _sender_platform.get("")
    sender_open_id = _sender_open_id.get("")
    if platform and sender_platform and sender_open_id:
        extra_env["OPENAGENTIC_SENDER_PLATFORM"] = sender_platform
        extra_env["OPENAGENTIC_SENDER_OPEN_ID"] = sender_open_id
    logger.info("_run_cli", binary=binary, cmd=" ".join(cmd[:6]),
                has_sender_context=bool(extra_env))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "LARK_CLI_NO_PROXY": "1", **extra_env},
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning("_run_cli non-zero exit", binary=binary, returncode=proc.returncode,
                       stderr=stderr.decode("utf-8", errors="replace")[:500])
    return {
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
        "stderr": stderr.decode("utf-8", errors="replace").strip(),
        "returncode": proc.returncode,
    }


async def _send_feishu_card(chat_id: str, markdown: str) -> dict[str, Any]:
    """通过飞书 SDK 发送交互卡片消息。

    若上下文中有思考卡片的 message_id（通过 contextvar _thinking_card_msg_id 传入），
    则更新该卡片而非创建新卡片，实现"思考中..."→结果的无缝替换。
    """
    import json as _json
    import os as _os

    app_id = _os.getenv("FEISHU_APP_ID", "")
    app_secret = _os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID/FEISHU_APP_SECRET not set in environment")

    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1.model.create_message_request import (
            CreateMessageRequest,
            CreateMessageRequestBody,
        )
        from lark_oapi.api.im.v1.model.patch_message_request import (
            PatchMessageRequest,
            PatchMessageRequestBody,
        )
    except ImportError:
        raise RuntimeError("lark-oapi not installed. Run: pip install lark-oapi") from None

    # 延迟 import——workflow module 不应强依赖 extensions
    from extensions.channels.feishu_card_utils import build_answer_card

    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .build()

    card = build_answer_card(markdown)
    card_json = _json.dumps(card, ensure_ascii=False)

    # 若有思考卡片 message_id，更新原卡片而非发新卡片
    thinking_id = _thinking_card_msg_id.get("")
    if thinking_id:
        patch_req = PatchMessageRequest.builder() \
            .message_id(thinking_id) \
            .request_body(PatchMessageRequestBody.builder()
                .content(card_json)
                .build()) \
            .build()
        patch_resp = await client.im.v1.message.apatch(patch_req)
        if patch_resp.code != 0:
            raise RuntimeError(f"Feishu card update failed: code={patch_resp.code} msg={patch_resp.msg}")
        logger.info("feishu card updated", message_id=thinking_id)
        return {"ok": True, "action": "updated", "message_id": thinking_id}

    req = CreateMessageRequest.builder() \
        .receive_id_type("chat_id") \
        .request_body(CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .content(card_json)
            .msg_type("interactive")
            .build()) \
        .build()

    resp = await client.im.v1.message.acreate(req)
    if resp.code != 0:
        raise RuntimeError(f"Feishu card send failed: code={resp.code} msg={resp.msg}")

    logger.info("feishu card sent", chat_id=chat_id,
                message_id=getattr(resp.data, "message_id", ""))
    return {
        "ok": True,
        "chat_id": chat_id,
        "message_id": getattr(resp.data, "message_id", ""),
    }


async def _execute_node(node_type: str, config: dict[str, Any]) -> Any:
    """执行单个节点（value/tool/llm/approval/human_input/feishu/wecom）。"""
    if node_type == "value":
        val = config.get("value")
        logger.debug("execute value node", value_preview=str(val)[:200])
        return val

    if node_type == "tool":
        name = config.get("tool_name")
        if not name:
            known = ", ".join(default_registry.list_tool_names())
            raise ValueError(
                f"tool node requires config.tool_name (known tools: {known})"
            )
        tool = default_registry.get(str(name))
        if tool is None:
            known = ", ".join(default_registry.list_tool_names())
            raise ValueError(f"Unknown tool '{name}' (known tools: {known})")
        # 工具入参支持两种形态：
        # 1) config.args: dict —— 直接透传给 tool.execute（推荐，能精确填 url/path/headers 等专属参数）
        # 2) config.arg: str  —— legacy 路径，把单字符串广播到 input/query/command 三个常用键，
        #    给 echo / calculator / run_command / knowledge_search 这类只吃单字符串的工具用
        args_dict = config.get("args")
        if isinstance(args_dict, dict):
            return await tool.execute(args_dict)
        arg = config.get("arg", "")
        if isinstance(arg, (dict, list)):
            arg = str(arg)
        logger.info("execute tool node", tool_name=name, arg_preview=str(arg)[:200])
        return await tool.execute({"input": str(arg), "query": str(arg), "command": str(arg)})

    if node_type == "llm":
        prompt = config.get("prompt")
        if not prompt:
            raise ValueError("llm node requires config.prompt")
        system = config.get("system_prompt")
        model = _resolve_validated_model(config.get("model"))
        logger.info("execute llm node", model=model or "(default)",
                    prompt_preview=str(prompt)[:200])
        messages = []
        if system:
            messages.append({"role": "system", "content": str(system)})
        messages.append({"role": "user", "content": str(prompt)})
        result = await chat_completion(messages=messages, model=model)
        return result["content"]

    if node_type == "feishu":
        subcommand = config.get("subcommand", "")
        if not subcommand:
            raise ValueError("feishu node requires config.subcommand")
        format_mode = config.get("format", "text")

        if format_mode == "card":
            chat_id = config.get("chat_id", "")
            content = config.get("content", "")
            if not chat_id:
                raise ValueError("feishu card node requires chat_id")
            if not content:
                raise ValueError("feishu card node requires content")
            return await _send_feishu_card(chat_id, content)

        # legacy CLI 模式（format: text 或未指定）
        args = config.get("args", [])
        if isinstance(args, str):
            args = [args]
        return await _run_cli("lark-cli", subcommand, args, platform="feishu")

    if node_type == "wecom":
        subcommand = config.get("subcommand", "")
        if not subcommand:
            raise ValueError("wecom node requires config.subcommand")
        args = config.get("args", [])
        if isinstance(args, str):
            args = [args]
        return await _run_cli("wecom-cli", subcommand, args, platform="wecom")

    if node_type == "approval":
        return {
            SUSPEND_FLAG: True,
            "suspend_type": "approval",
            "channel": config.get("channel", "feishu"),
            "instance_key": config.get("approval_code", ""),
            "approval_config": config.get("approval_config", {}),
        }

    if node_type == "human_input":
        return {
            SUSPEND_FLAG: True,
            "suspend_type": "human_input",
            "channel": config.get("channel", "feishu"),
            "instance_key": config.get("instance_key", ""),
            "prompt": config.get("prompt", ""),
            "input_config": config.get("input_config", {}),
        }

    if node_type == "evaluator":
        # evaluator 节点：LLM 对 target_node 输出按 criteria 评分
        from openagentic.workflow.evaluator import execute_evaluator
        return await execute_evaluator(
            target_output=config.get("target_output"),
            criteria=config.get("criteria", ""),
            min_score=float(config.get("min_score", 0.7)),
            model=config.get("model"),
            api_base=config.get("api_base"),
            api_key=config.get("api_key"),
        )

    raise ValueError(f"Unsupported node type: {node_type}")


def _resolve_validated_model(model: str | None) -> str | None:
    """校验 workflow 中指定的 model 是否在 provider 白名单中，无效则回退到服务器默认。

    AI 创建 workflow 时可能硬编码不支持的模型（如 gpt-4o），
    这里做个兜底：只承认 provider store 中已配置的模型，其余一律回退 None。
    """
    if not model:
        return None
    store = get_provider_store()
    config = store.get()
    for profile in config.profiles:
        if profile.enabled and model in profile.models:
            return model
    # 模型不在任何 provider 白名单中，回退默认
    return None


def _render_value(value: Any, context: dict[str, Any]) -> Any:
    """递归渲染模板变量，支持 dict/list/str。"""
    if isinstance(value, dict):
        return {k: _render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(v, context) for v in value]
    if isinstance(value, str):
        return _render_template(value, context)
    return value


def _render_template(template: str, context: dict[str, Any]) -> str:
    """渲染形如 {{input.xxx}} / {{nodes.n1}} 的模板字符串。"""
    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        resolved = _resolve_expr(context, expr)
        if resolved is None:
            return ""
        return str(resolved)

    return VAR_PATTERN.sub(_replace, template)


def _resolve_expr(context: dict[str, Any], expr: str) -> Any:
    cur: Any = context
    for part in expr.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """评估条件边表达式，支持三种形式：

    - ``{{nodes.x}} == "value"``  → 字符串相等
    - ``{{nodes.x}} != "value"``  → 字符串不等
    - ``{{nodes.x}}``             → 真值检查（非 None / 非空字符串）

    注意：先做模式匹配再求值，避免模板渲染把表达式变成字面字符串。
    """
    cond = condition.strip()

    # 1. 精确匹配：== "value"（先匹配模式，再从 context 取实际值比较）
    m = _COND_EQ_RE.match(cond)
    if m:
        val = _resolve_expr(context, m.group(1))
        return str(val) == m.group(2) if val is not None else False

    # 2. 精确匹配：!= "value"
    m = _COND_NE_RE.match(cond)
    if m:
        val = _resolve_expr(context, m.group(1))
        return str(val) != m.group(2) if val is not None else True

    # 3. 真值表达式：{{nodes.x}}
    m = _COND_TRUTHY_RE.match(cond)
    if m:
        val = _resolve_expr(context, m.group(1))
        return val is not None and val != "" and val != "None" and val != "False"

    # 4. 兜底：模板渲染后做真值判断（支持含字面量的混合表达式）
    rendered = _render_template(cond, context)
    if rendered != cond:
        return bool(rendered) and rendered not in ("None", "False", "")
    return False


def _should_skip_node(
    node_id: str,
    definition: dict[str, Any],
    outputs: dict[str, Any],
) -> tuple[bool, str]:
    """判断节点是否应被跳过（条件边未满足）。

    返回 (should_skip, reason)。
    - 若所有入边都有 condition 且全部为 False → 跳过
    - 若至少有一条入边无条件或条件为 True → 执行
    """
    edges = definition.get("edges", [])
    incoming = [e for e in edges if e.get("to") == node_id]
    if not incoming:
        return False, ""  # 入度为 0 的节点（如 input）始终执行

    context = {"nodes": outputs}
    has_unconditional = False
    any_true = False
    reasons: list[str] = []
    for edge in incoming:
        cond = edge.get("condition")
        if not cond:
            has_unconditional = True
            break
        if _evaluate_condition(cond, context):
            any_true = True
            break
        else:
            reasons.append(f"{edge['from']}→{node_id}: {cond}=False")

    if has_unconditional or any_true:
        return False, ""
    return True, "; ".join(reasons)

