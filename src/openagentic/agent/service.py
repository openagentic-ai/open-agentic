"""模块说明（中文）：`src/openagentic/agent/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

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
    """列出当前用户的 Agent，按更新时间倒序。"""
    result = await db.execute(
        select(Agent).where(Agent.user_id == user_id).order_by(Agent.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_agent(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID) -> Agent | None:
    """按 ID + 所属用户查询 Agent，避免越权访问。"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_agent(db: AsyncSession, user_id: uuid.UUID, body: AgentCreate) -> Agent:
    """创建 Agent。

    若用户未显式传工具列表，默认启用当前注册表中的全部内置工具。
    """
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
    """部分更新 Agent；tools 字段会先做合法性过滤。"""
    patch = body.model_dump(exclude_unset=True)
    if "tools" in patch and patch["tools"] is not None:
        patch["tools"] = _filter_tool_names(patch["tools"])
    for field, value in patch.items():
        setattr(agent, field, value)
    await db.flush()
    return agent


async def delete_agent(db: AsyncSession, agent: Agent) -> None:
    """删除 Agent 实体。"""
    await db.delete(agent)


async def list_executions(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentExecution]:
    """查询某 Agent 的执行历史。"""
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
    """执行 Agent 并记录结果。

    设计说明：
    - 无论执行成功或失败，都会写入一条 execution；
    - 失败场景会把异常信息写入 `steps`，便于后续排查。
    """
    status = ExecutionStatus.completed
    answer = ""
    steps: list[dict] = []
    started_at = datetime.now(timezone.utc)

    try:
        answer, steps = await executor.run(agent, user_input)
    except Exception as exc:
        # 执行失败时降级为统一错误文案，同时保留异常细节供审计。
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
    """过滤并去重工具名，只保留当前注册表存在的工具。"""
    if not tool_names:
        return []
    available = set(default_registry.list_tool_names())
    deduped: list[str] = []
    for name in tool_names:
        if name in available and name not in deduped:
            deduped.append(name)
    return deduped

