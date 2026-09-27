import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.control_plane.employee_registry import get_employee_role
from openagentic.control_plane.system1 import route_task
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.tasks.models import Task, TaskStatus
from openagentic.tasks.schemas import TaskCreate, TaskResponse, TaskUpdate
from openagentic.tasks.service import transition

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

TASK_ROUTING_ENV = "OPENAGENTIC_TASK_ROUTING_ENABLED"


def _task_routing_enabled() -> bool:
    return os.environ.get(TASK_ROUTING_ENV, "").strip().lower() in {"1", "true", "yes"}


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    metadata: dict = {}
    initial_status = TaskStatus.DRAFT
    if _task_routing_enabled():
        routing = await route_task(body.title, body.description or "")
        if routing is not None:
            metadata["routing"] = routing.as_dict()
            role = get_employee_role(routing.role)
            if role is not None:
                metadata["employee"] = {
                    "role": role.key,
                    "department": role.department,
                    "title": role.title,
                }
            approval_required = routing.needs_human_decision or routing.risk == "high"
            metadata["approval"] = {
                "required": approval_required,
                "status": "pending" if approval_required else "not_required",
            }
            metadata["queue"] = {"status": "waiting_approval" if approval_required else "ready"}
            initial_status = TaskStatus.WAITING_USER if approval_required else TaskStatus.PLANNED

    task = Task(user_id=current.id, metadata_json=metadata, status=initial_status, **body.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    query = select(Task).where(Task.user_id == current.id).order_by(Task.created_at.desc())
    if status_filter is not None:
        query = query.where(Task.status == status_filter)
    return list((await db.scalars(query)).all())


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, body: TaskUpdate, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.user_id == current.id))
    if task is None:
        raise HTTPException(404, "Task not found")
    values = body.model_dump(exclude_unset=True)
    if "status" in values:
        try:
            transition(task, values.pop("status"))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    for key, value in values.items():
        setattr(task, key, value)
    await db.commit()
    await db.refresh(task)
    return task


async def _set_control_status(task_id: UUID, target: TaskStatus, current: User, db: AsyncSession) -> Task:
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.user_id == current.id))
    if task is None:
        raise HTTPException(404, "Task not found")
    try:
        transition(task, target)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(task_id: UUID, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _set_control_status(task_id, TaskStatus.WAITING_USER, current, db)


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: UUID, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _set_control_status(task_id, TaskStatus.RUNNING, current, db)


@router.post("/{task_id}/approve", response_model=TaskResponse)
async def approve_task(task_id: UUID, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """本人批准任务进入可执行队列。"""
    task = await db.scalar(select(Task).where(Task.id == task_id, Task.user_id == current.id))
    if task is None:
        raise HTTPException(404, "Task not found")
    if task.status not in {TaskStatus.DRAFT, TaskStatus.WAITING_USER}:
        raise HTTPException(409, "Task is not waiting for approval")
    task.status = TaskStatus.PLANNED
    metadata = dict(task.metadata_json or {})
    approval = metadata.setdefault("approval", {})
    approval.update({"required": False, "status": "approved"})
    queue = metadata.setdefault("queue", {})
    queue["status"] = "ready"
    task.metadata_json = metadata
    await db.commit()
    await db.refresh(task)
    return task
