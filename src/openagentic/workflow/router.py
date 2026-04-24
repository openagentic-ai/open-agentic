"""模块说明（中文）：`src/openagentic/workflow/router.py`。\n\n该文件定义 HTTP 路由与请求入口，负责参数校验与服务层调用。\n"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.workflow import schemas, service
from openagentic.workflow.runtime import runtime

router = APIRouter(prefix="/api", tags=["workflow"])


@router.get("/workflows", response_model=list[schemas.WorkflowResponse])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_workflows(db, current_user.id)


@router.post("/workflows", response_model=schemas.WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: schemas.WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.create_workflow(db, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workflows/{workflow_id}", response_model=schemas.WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await service.get_workflow(db, workflow_id, current_user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/workflows/{workflow_id}", response_model=schemas.WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: schemas.WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await service.get_workflow(db, workflow_id, current_user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        return await service.update_workflow(db, workflow, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await service.get_workflow(db, workflow_id, current_user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await service.delete_workflow(db, workflow)


@router.post("/workflows/{workflow_id}/runs", response_model=schemas.WorkflowExecutionResponse)
async def start_workflow_run(
    workflow_id: uuid.UUID,
    body: schemas.WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await service.get_workflow(db, workflow_id, current_user.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow.is_active:
        raise HTTPException(status_code=400, detail="Workflow is inactive")

    run = await service.create_run(db, workflow, body.input_data)
    return await service.execute_run(db, run, workflow)


@router.get("/workflow-runs", response_model=list[schemas.WorkflowExecutionResponse])
async def list_workflow_runs(
    workflow_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_runs(db, current_user.id, workflow_id)


@router.get("/workflow-runs/{run_id}", response_model=schemas.WorkflowExecutionResponse)
async def get_workflow_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await service.get_run(db, run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.post("/workflow-runs/{run_id}/cancel", response_model=schemas.WorkflowExecutionResponse)
async def cancel_workflow_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await service.get_run(db, run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    run = await service.request_cancel(db, run)
    runtime.cancel(run.id)
    return run

