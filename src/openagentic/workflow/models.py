"""模块说明（中文）：`src/openagentic/workflow/models.py`。\n\n该文件定义数据库模型与持久化结构。\n"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NodeType(str, enum.Enum):
    start = "start"
    end = "end"
    llm = "llm"
    agent = "agent"
    condition = "condition"
    code = "code"
    http = "http"
    knowledge = "knowledge"


class ExecutionStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    suspended = "suspended"  # 节点级挂起，等飞书/企微回调或人工输入 → 唤醒后回 running
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# 终态：到达后不再流转
TERMINAL_STATUSES = frozenset(
    {ExecutionStatus.completed, ExecutionStatus.failed, ExecutionStatus.cancelled}
)


# Backward-compatible alias kept for existing API/tests.
WorkflowRunStatus = ExecutionStatus


class Workflow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflows"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    executions = relationship("WorkflowExecution", back_populates="workflow", lazy="selectin")


class WorkflowExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_executions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.pending, nullable=False
    )
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    node_states: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow = relationship("Workflow", back_populates="executions")
