"""模块说明（中文）：`src/openagentic/agent/router.py`。

Agent HTTP API 路由：CRUD + 执行 + 执行历史查询。
所有端点均需 JWT 鉴权，user_id 行级隔离。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent import schemas, service
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.deps import get_current_user

router = APIRouter(prefix="/api", tags=["agent"])


@router.get("/agents", response_model=list[schemas.AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有 Agent（按更新时间倒序）。"""
    return await service.list_agents(db, current_user.id)


@router.post("/agents", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: schemas.AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 Agent（工具列表默认启用全部内置工具）。"""
    return await service.create_agent(db, current_user.id, body)


@router.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按 ID 查询 Agent，校验归属用户（越权返回 404）。"""
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/agents/{agent_id}", response_model=schemas.AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: schemas.AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """部分更新 Agent（仅传入字段生效）。"""
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await service.update_agent(db, agent, body)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 Agent 实体。"""
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await service.delete_agent(db, agent)


@router.post("/agents/{agent_id}/execute", response_model=schemas.ExecutionResponse)
async def execute_agent(
    agent_id: uuid.UUID,
    body: schemas.AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行 Agent：运行 ReAct loop，返回执行记录（含步骤追踪）。

    通过并发底座接入：session_key=user_id 让同用户的连续调用串行（避免对账面打架），
    跨用户走全局信号量与 LLM 类别限流。底层 litellm_chat 还会再过一道 LLM 类别。
    """
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from openagentic.concurrency import get_default_gate, GateBusy, GateTimeout
    try:
        return await get_default_gate().submit(
            session_key=str(current_user.id),
            coro_factory=lambda: service.execute_agent(db, agent, body.input),
        )
    except GateBusy:
        raise HTTPException(status_code=503, detail="Service busy, please retry shortly")
    except GateTimeout:
        raise HTTPException(status_code=504, detail="Execution timed out")


@router.get("/agents/{agent_id}/executions", response_model=list[schemas.ExecutionResponse])
async def list_executions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询某 Agent 的所有执行历史（按创建时间倒序）。"""
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await service.list_executions(db, agent.id)
