"""Pydantic schemas for Phase 2 agent APIs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from openagentic.agent.models import AgentStatus, ExecutionStatus


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    tool_names: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    status: AgentStatus | None = None
    tool_names: list[str] | None = None


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    model: str | None
    system_prompt: str | None
    status: AgentStatus
    tool_names: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentExecuteRequest(BaseModel):
    input: str = Field(min_length=1)


class AgentStep(BaseModel):
    step: str
    thought: str | None = None
    action: str | None = None
    observation: str | None = None


class AgentExecutionResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    input_text: str
    output_text: str
    status: ExecutionStatus
    trace: list[AgentStep]
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    sessionId: str | None = None
    agentId: str | None = None


class AgentMessageResponse(BaseModel):
    message: str
    execution_id: uuid.UUID | None = None

