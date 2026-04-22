"""Agent system database models for Phase 2."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentStatus(str, enum.Enum):
    online = "online"
    idle = "idle"
    offline = "offline"


class ExecutionStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus), default=AgentStatus.idle, nullable=False
    )
    tool_names: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    executions = relationship(
        "AgentExecution",
        back_populates="agent",
        lazy="selectin",
        order_by="desc(AgentExecution.created_at)",
    )


class AgentExecution(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_executions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.success, nullable=False
    )
    trace: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")

    agent = relationship("Agent", back_populates="executions")

