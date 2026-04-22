"""Agent API routes for Phase 2."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    return await service.list_agents(db, current_user.id)


@router.post("/agents", response_model=schemas.AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: schemas.AgentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_agent(db, current_user.id, body)


@router.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await service.delete_agent(db, agent)


@router.post("/agents/{agent_id}/execute", response_model=schemas.AgentExecutionResponse)
async def execute_agent(
    agent_id: uuid.UUID,
    body: schemas.AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await service.execute_agent(db, agent, body.input)


@router.get("/agents/{agent_id}/executions", response_model=list[schemas.AgentExecutionResponse])
async def list_executions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await service.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await service.list_executions(db, agent.id)


@router.post("/agent/message", response_model=schemas.AgentMessageResponse)
async def agent_message(
    body: schemas.AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    create_if_missing: bool = Query(
        True,
        description="When no agent exists, auto-create one with default tools.",
    ),
):
    agent = None
    if body.agentId:
        try:
            agent = await service.get_agent(db, uuid.UUID(body.agentId), current_user.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid agentId") from exc

    if not agent:
        agents = await service.list_agents(db, current_user.id)
        if agents:
            agent = agents[0]

    if not agent and create_if_missing:
        agent = await service.create_agent(
            db,
            current_user.id,
            schemas.AgentCreate(name="Default Agent", tool_names=service.tool_registry.list_tools()),
        )

    if not agent:
        raise HTTPException(status_code=404, detail="No available agent")

    execution = await service.execute_agent(db, agent, body.message)
    return schemas.AgentMessageResponse(message=execution.output_text, execution_id=execution.id)

