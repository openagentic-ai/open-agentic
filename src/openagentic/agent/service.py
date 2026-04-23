"""Agent business services for Phase 2."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent.models import Agent, AgentExecution, ExecutionStatus
from openagentic.agent.react import ReactExecutor
from openagentic.agent.schemas import AgentCreate, AgentUpdate
from openagentic.agent.tools import default_registry

executor = ReactExecutor(default_registry)


async def list_agents(db: AsyncSession, user_id: uuid.UUID) -> list[Agent]:
    result = await db.execute(
        select(Agent).where(Agent.user_id == user_id).order_by(Agent.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_agent(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID) -> Agent | None:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_agent(db: AsyncSession, user_id: uuid.UUID, body: AgentCreate) -> Agent:
    clean_tools = _filter_tool_names(body.tools)
    if not clean_tools:
        clean_tools = default_registry.list_tool_names()

    agent = Agent(
        user_id=user_id,
        name=body.name,
        description=body.description,
        model=body.model,
        system_prompt=body.system_prompt,
        tools=clean_tools,
        config=body.config or {},
        is_active=True,
    )
    db.add(agent)
    await db.flush()
    return agent


async def update_agent(
    db: AsyncSession, agent: Agent, body: AgentUpdate
) -> Agent:
    patch = body.model_dump(exclude_unset=True)
    if "tools" in patch and patch["tools"] is not None:
        patch["tools"] = _filter_tool_names(patch["tools"])
    for field, value in patch.items():
        setattr(agent, field, value)
    await db.flush()
    return agent


async def delete_agent(db: AsyncSession, agent: Agent) -> None:
    await db.delete(agent)


async def list_executions(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentExecution]:
    result = await db.execute(
        select(AgentExecution)
        .where(AgentExecution.agent_id == agent_id)
        .order_by(AgentExecution.created_at.desc())
    )
    return list(result.scalars().all())


async def execute_agent(
    db: AsyncSession,
    agent: Agent,
    user_input: str,
) -> AgentExecution:
    status = ExecutionStatus.completed
    answer = ""
    steps: list[dict] = []
    started_at = datetime.now(timezone.utc)

    try:
        answer, steps = await executor.run(agent, user_input)
    except Exception as exc:
        status = ExecutionStatus.failed
        answer = "执行失败，请查看错误信息。"
        steps = [{"step": "error", "observation": str(exc)}]

    execution = AgentExecution(
        agent_id=agent.id,
        user_id=agent.user_id,
        input=user_input,
        output=answer,
        status=status,
        steps=steps,
        token_total=0,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.flush()
    return execution


def _filter_tool_names(tool_names: list[str]) -> list[str]:
    if not tool_names:
        return []
    available = set(default_registry.list_tool_names())
    deduped: list[str] = []
    for name in tool_names:
        if name in available and name not in deduped:
            deduped.append(name)
    return deduped

