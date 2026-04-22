"""Workflow business logic and execution engine."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent.tools import ToolRegistry
from openagentic.core.llm.service import chat_completion
from openagentic.db.session import async_session
from openagentic.workflow.models import Workflow, WorkflowRun, WorkflowRunStatus
from openagentic.workflow.schemas import WorkflowCreate, WorkflowUpdate

VAR_PATTERN = re.compile(r"\{\{\s*([^}]+)\s*\}\}")

tool_registry = ToolRegistry()


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
        if node_type not in {"value", "tool", "llm"}:
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
    validate_definition(body.definition)
    workflow = Workflow(
        user_id=user_id,
        name=body.name,
        description=body.description,
        definition=body.definition,
        is_active=body.is_active,
    )
    db.add(workflow)
    await db.flush()
    return workflow


async def update_workflow(db: AsyncSession, workflow: Workflow, body: WorkflowUpdate) -> Workflow:
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
    input_payload: dict[str, Any],
) -> WorkflowRun:
    run = WorkflowRun(
        workflow_id=workflow.id,
        user_id=workflow.user_id,
        status=WorkflowRunStatus.pending,
        input_payload=input_payload,
        trace=[],
    )
    db.add(run)
    await db.flush()
    return run


async def list_runs(
    db: AsyncSession, user_id: uuid.UUID, workflow_id: uuid.UUID | None = None
) -> list[WorkflowRun]:
    stmt = select(WorkflowRun).where(WorkflowRun.user_id == user_id).order_by(WorkflowRun.created_at.desc())
    if workflow_id:
        stmt = stmt.where(WorkflowRun.workflow_id == workflow_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_run(db: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID) -> WorkflowRun | None:
    result = await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def request_cancel(db: AsyncSession, run: WorkflowRun) -> WorkflowRun:
    run.cancel_requested = True
    await db.flush()
    return run


async def execute_run(db: AsyncSession, run: WorkflowRun, workflow: Workflow) -> WorkflowRun:
    run.status = WorkflowRunStatus.running
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = None
    run.error = None
    run.output_payload = None
    run.trace = []
    await db.flush()

    try:
        output, trace = await _execute_definition(
            db=db,
            run=run,
            definition=workflow.definition,
            input_payload=run.input_payload,
        )
        if run.cancel_requested:
            run.status = WorkflowRunStatus.cancelled
        else:
            run.status = WorkflowRunStatus.success
        run.output_payload = {"result": output}
        run.trace = trace
    except asyncio.CancelledError:
        run.status = WorkflowRunStatus.cancelled
        run.error = "Run cancelled"
    except Exception as exc:
        run.status = WorkflowRunStatus.failed
        run.error = str(exc)
    finally:
        run.finished_at = datetime.now(timezone.utc)
        await db.flush()
    return run


async def execute_run_by_id(run_id: uuid.UUID, workflow_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with async_session() as db:
        run = await get_run(db, run_id, user_id)
        workflow = await get_workflow(db, workflow_id, user_id)
        if not run or not workflow:
            return
        await execute_run(db, run, workflow)
        await db.commit()


def _topological_order(definition: dict[str, Any]) -> list[str]:
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
    run: WorkflowRun,
    definition: dict[str, Any],
    input_payload: dict[str, Any],
) -> tuple[Any, list[dict[str, Any]]]:
    nodes = {n["id"]: n for n in definition.get("nodes", [])}
    order = _topological_order(definition)
    outputs: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []

    for node_id in order:
        await db.refresh(run)
        if run.cancel_requested:
            trace.append({"node_id": node_id, "status": "cancelled", "reason": "cancel_requested"})
            break

        node = nodes[node_id]
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


async def _execute_node(node_type: str, config: dict[str, Any]) -> Any:
    if node_type == "value":
        return config.get("value")

    if node_type == "tool":
        name = config.get("tool_name")
        if not name:
            raise ValueError("tool node requires config.tool_name")
        arg = config.get("arg", "")
        if isinstance(arg, (dict, list)):
            arg = str(arg)
        return tool_registry.call(name, str(arg))

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

    raise ValueError(f"Unsupported node type: {node_type}")


def _render_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(v, context) for v in value]
    if isinstance(value, str):
        return _render_template(value, context)
    return value


def _render_template(template: str, context: dict[str, Any]) -> str:
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

