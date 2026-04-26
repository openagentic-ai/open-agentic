"""模块说明（中文）：`src/openagentic/agent/models.py`。

Agent 模块数据库模型：Agent 定义表 + Agent 执行历史表。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExecutionStatus(str, enum.Enum):
    """Agent / Workflow 执行状态枚举。"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Agent 定义表。

    每个 Agent 属于一个用户，包含 system prompt、模型选择、工具列表等配置。
    """
    __tablename__ = "agents"

    # 行级隔离：通过 user_id 确保只能访问自己创建的 Agent
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # system prompt：传给 LLM 的角色设定
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # model：LiteLLM 格式的模型标识（如 deepseek/deepseek-v4-pro）
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # tools：启用的工具名称列表，JSON 存储
    tools: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    # config：扩展配置（如 temperature、max_tokens 等）
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    executions = relationship("AgentExecution", back_populates="agent", lazy="selectin")


class AgentExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Agent 执行记录表。

    每次调用 Agent 产生一条记录，包含输入、输出、步骤追踪和 token 统计。
    """
    __tablename__ = "agent_executions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.pending, nullable=False
    )
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # steps：ReAct 执行步骤 JSON 数组，用于审计与调试
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    token_total: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    agent = relationship("Agent", back_populates="executions")
