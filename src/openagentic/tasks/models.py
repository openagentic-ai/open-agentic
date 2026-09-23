from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaskStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """跨端共享的个人任务；执行实例后续挂在此模型上。"""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"), default=TaskStatus.DRAFT, nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
