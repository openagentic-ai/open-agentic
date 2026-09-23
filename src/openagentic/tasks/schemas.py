from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from openagentic.tasks.models import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source: str | None = Field(default=None, max_length=100)
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None
    blocked_reason: str | None = None


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    source: str | None
    due_at: datetime | None
    next_run_at: datetime | None
    blocked_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
