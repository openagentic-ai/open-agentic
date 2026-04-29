"""模块说明（中文）：`src/openagentic/workflow/schemas.py`。

工作流模块请求/响应数据结构。

definition 格式示例：
{
  "nodes": [{"id": "start", "type": "value", "config": {"value": "hello"}},
            {"id": "llm1", "type": "llm", "config": {"prompt": "..."}}],
  "edges": [{"from": "start", "to": "llm1"}]
}
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    """创建工作流请求：名称 + DAG 定义（nodes/edges）。"""
    name: str = Field(..., max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    definition: dict = Field(..., description="DAG definition with nodes and edges")


class WorkflowUpdate(BaseModel):
    """更新工作流请求（所有字段可选）。"""
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    is_active: bool | None = None


class WorkflowResponse(BaseModel):
    """工作流查询响应。"""
    id: uuid.UUID
    name: str
    slug: str | None = None
    description: str | None = None
    definition: dict
    version: int = 1
    is_active: bool = True
    is_system: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunRequest(BaseModel):
    """启动工作流执行请求。"""
    input_data: dict | None = None


class WorkflowExecutionResponse(BaseModel):
    """工作流执行记录响应。"""
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
    """工作流节点定义 schema（文档用途）。"""
    id: str
    type: str
    config: dict = Field(default_factory=dict)
    position: dict | None = None


class EdgeDefinition(BaseModel):
    """工作流边定义 schema（文档用途）。"""
    source: str
    target: str
    condition: str | None = None
