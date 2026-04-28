"""模块说明（中文）：`src/openagentic/workflow/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent.tools import default_registry
from openagentic.core.llm.service import chat_completion
from openagentic.db.session import async_session
from openagentic.workflow.models import TERMINAL_STATUSES, ExecutionStatus, Workflow, WorkflowExecution
from openagentic.workflow.schemas import WorkflowCreate, WorkflowUpdate

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
        select(Workflow).where(Workflow.user_id == user_id).order_by(Workflow.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    return result.scalar_one_or_none()


def validate_definition(definition: dict[str, Any]) -> None:
    """校验工作流定义是否合法。

    重点检查：
    - nodes/edges 结构；
    - 节点 ID 唯一性；
    - 节点类型是否支持；
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
        if node_type not in {"value", "tool", "llm", "approval", "human_input", "feishu", "wecom"}:
            raise ValueError(f"Unsupported node type: {node_type}")
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
        description=body.description,
        definition=body.definition,
        is_active=True,
    )
    db.add(workflow)
    await db.flush()
    return workflow


async def update_workflow(db: AsyncSession, workflow: Workflow, body: WorkflowUpdate) -> Workflow:
    """更新工作流；若 definition 被修改，会再次校验。"""
    patch = body.model_dump(exclude_unset=True)
    if "definition" in patch and patch["definition"] is not None:
        validate_definition(patch["definition"])
    for field, value in patch.items():
        setattr(workflow, field, value)
    await db.flush()
    return workflow


async def delete_workflow(db: AsyncSession, workflow: Workflow) -> None:
    await db.delete(workflow)


async def create_run(
    db: AsyncSession,
    workflow: Workflow,
    input_data: dict[str, Any] | None,
) -> WorkflowExecution:
    """创建一次运行记录（初始状态 pending）。"""
    run = WorkflowExecution(
        workflow_id=workflow.id,
        user_id=workflow.user_id,
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


async def execute_run(db: AsyncSession, run: WorkflowExecution, workflow: Workflow) -> WorkflowExecution:
    """执行单次 Run。

    状态流转：
    pending -> running -> completed/failed/cancelled
    中途可进入 suspended（approval/human_input 节点触发），
    resume 时从 suspended 回到 running。
    """
    run.status = ExecutionStatus.running
    run.started_at = datetime.now(timezone.utc)
    run.completed_at = None
    run.output_data = None
    run.node_states = {TRACE_KEY: []}
    await db.flush()

    try:
        output, trace = await _execute_definition(
            db=db,
            run=run,
            definition=workflow.definition,
            input_payload=run.input_data or {},
        )
        if _is_cancel_requested(run):
            run.status = ExecutionStatus.cancelled
        elif run.status == ExecutionStatus.suspended:
            # _execute_definition 已将 run 置为 suspended 并持久化了 outputs/trace
            pass
        else:
            run.status = ExecutionStatus.completed
        if run.status != ExecutionStatus.suspended:
            run.output_data = {"result": output}
            run.node_states = {**(run.node_states or {}), TRACE_KEY: trace}
    except asyncio.CancelledError:
        # 外部协程取消（如任务终止）统一映射为 cancelled。
        run.status = ExecutionStatus.cancelled
        run.node_states = {**(run.node_states or {}), "error": "Run cancelled"}
    except Exception as exc:
        run.status = ExecutionStatus.failed
        run.node_states = {**(run.node_states or {}), "error": str(exc)}
    finally:
        if run.status in TERMINAL_STATUSES:
            run.completed_at = datetime.now(timezone.utc)
        await db.flush()
    return run


async def execute_run_by_id(run_id: uuid.UUID, workflow_id: uuid.UUID, user_id: uuid.UUID) -> None:
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
) -> tuple[Any, list[dict[str, Any]]]:
    """按拓扑序执行整个定义并生成 trace。"""
    nodes = {n["id"]: n for n in definition.get("nodes", [])}
    order = _topological_order(definition)
    outputs: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []

    for node_id in order:
        await db.refresh(run)
        if _is_cancel_requested(run):
            trace.append({"node_id": node_id, "status": "cancelled", "reason": "cancel_requested"})
            break

        node = nodes[node_id]

        # 条件边检查：入边条件全部为 False 时跳过此节点
        should_skip, skip_reason = _should_skip_node(node_id, definition, outputs)
        if should_skip:
            trace.append({
                "node_id": node_id,
                "node_type": node["type"],
                "status": "skipped",
                "reason": skip_reason,
            })
            continue

        rendered = _render_value(
            node.get("config", {}),
            {"input": input_payload, "nodes": outputs},
        )

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
                        "node_type": node["type"],
                        "status": "suspended",
                        "waiting_for": signal,
                    })
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
                trace.append(
                    {
                        "node_id": node_id,
                        "node_type": node["type"],
                        "status": "success",
                        "attempt": attempts,
                        "output": output,
                    }
                )
                break
            except Exception as exc:  # noqa: PERF203
                # 失败后根据 retries 决定重试或失败终止，并记录结构化 trace。
                last_err = str(exc)
                if attempts > retries:
                    trace.append(
                        {
                            "node_id": node_id,
                            "node_type": node["type"],
                            "status": "failed",
                            "attempt": attempts,
                            "error": last_err,
                        }
                    )
                    raise RuntimeError(f"Node {node_id} failed: {last_err}") from exc
                trace.append(
                    {
                        "node_id": node_id,
                        "node_type": node["type"],
                        "status": "retrying",
                        "attempt": attempts,
                        "error": last_err,
                    }
                )

    final_output = outputs[order[-1]] if order and order[-1] in outputs else None
    return final_output, trace


async def _run_cli(binary: str, subcommand: str, args: list) -> dict[str, Any]:
    """执行 CLI 二进制，返回 {stdout, stderr, returncode}。"""
    cmd = [binary] + subcommand.split() + [str(a) for a in args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return {
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
        "stderr": stderr.decode("utf-8", errors="replace").strip(),
        "returncode": proc.returncode,
    }


async def _execute_node(node_type: str, config: dict[str, Any]) -> Any:
    """执行单个节点（value/tool/llm/approval/human_input/feishu/wecom）。"""
    if node_type == "value":
        return config.get("value")

    if node_type == "tool":
        name = config.get("tool_name")
        if not name:
            raise ValueError("tool node requires config.tool_name")
        tool = default_registry.get(str(name))
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        arg = config.get("arg", "")
        if isinstance(arg, (dict, list)):
            arg = str(arg)
        return await tool.execute({"input": str(arg), "query": str(arg), "command": str(arg)})

    if node_type == "llm":
        prompt = config.get("prompt")
        if not prompt:
            raise ValueError("llm node requires config.prompt")
        system = config.get("system_prompt")
        model = config.get("model")
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
        args = config.get("args", [])
        if isinstance(args, str):
            args = [args]
        return await _run_cli("lark-cli", subcommand, args)

    if node_type == "wecom":
        subcommand = config.get("subcommand", "")
        if not subcommand:
            raise ValueError("wecom node requires config.subcommand")
        args = config.get("args", [])
        if isinstance(args, str):
            args = [args]
        return await _run_cli("wecom-cli", subcommand, args)

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

    raise ValueError(f"Unsupported node type: {node_type}")


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

