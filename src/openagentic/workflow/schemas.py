"""Workflow Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    definition: dict = Field(..., description="DAG definition with nodes and edges")


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    is_active: bool | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    definition: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunRequest(BaseModel):
    input_data: dict | None = None


class WorkflowExecutionResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    input_data: dict | None
    output_data: dict | None
    node_states: dict
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NodeDefinition(BaseModel):
    """Schema for documenting node structure within a workflow definition."""
    id: str
    type: str
    config: dict = Field(default_factory=dict)
    position: dict | None = None


class EdgeDefinition(BaseModel):
    """Schema for documenting edge structure within a workflow definition."""
    source: str
    target: str
    condition: str | None = None
