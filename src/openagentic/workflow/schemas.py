"""Pydantic schemas for workflow APIs."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from openagentic.workflow.models import WorkflowRunStatus


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    definition: dict[str, Any] | None = None
    is_active: bool | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    definition: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = True


class WorkflowRunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: WorkflowRunStatus
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None
    trace: list[dict[str, Any]]
    error: str | None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}

