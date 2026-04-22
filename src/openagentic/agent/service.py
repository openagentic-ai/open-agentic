"""Agent business services for Phase 2."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.agent.models import Agent, AgentExecution, AgentStatus, ExecutionStatus
from openagentic.agent.react import ReactExecutor
from openagentic.agent.schemas import AgentCreate, AgentStep, AgentUpdate
from openagentic.agent.tools import ToolRegistry

tool_registry = ToolRegistry()
executor = ReactExecutor(tool_registry)


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
    clean_tools = _filter_tool_names(body.tool_names)
    if not clean_tools:
        clean_tools = tool_registry.list_tools()

    agent = Agent(
        user_id=user_id,
        name=body.name,
        description=body.description,
        model=body.model,
        system_prompt=body.system_prompt,
        status=AgentStatus.idle,
        tool_names=clean_tools,
    )
    db.add(agent)
    await db.flush()
    return agent


async def update_agent(
    db: AsyncSession, agent: Agent, body: AgentUpdate
) -> Agent:
    patch = body.model_dump(exclude_unset=True)
    if "tool_names" in patch and patch["tool_names"] is not None:
        patch["tool_names"] = _filter_tool_names(patch["tool_names"])
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
    answer = ""
    steps: list[AgentStep] = []
    status = ExecutionStatus.success
    error = None

    try:
        answer, steps = await executor.run(agent, user_input)
    except Exception as exc:
        status = ExecutionStatus.failed
        error = str(exc)
        answer = "执行失败，请查看错误信息。"
        steps = [AgentStep(step="error", thought="执行器抛出异常", observation=str(exc))]

    execution = AgentExecution(
        agent_id=agent.id,
        input_text=user_input,
        output_text=answer,
        status=status,
        trace=[step.model_dump() for step in steps],
        error=error,
    )
    db.add(execution)
    agent.status = AgentStatus.online if status == ExecutionStatus.success else AgentStatus.offline
    await db.flush()
    return execution


def _filter_tool_names(tool_names: list[str]) -> list[str]:
    if not tool_names:
        return []
    available = set(tool_registry.list_tools())
    deduped: list[str] = []
    for name in tool_names:
        if name in available and name not in deduped:
            deduped.append(name)
    return deduped

