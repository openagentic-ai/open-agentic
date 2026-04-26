"""模块说明（中文）：`src/openagentic/core/llm/schemas.py`。

LLM 模块请求/响应数据结构。
"""

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """模型基本信息。"""
    id: str
    name: str
    provider: str


class TokenUsage(BaseModel):
    """Token 使用量统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProviderProfileUpdate(BaseModel):
    """Provider 配置更新请求（所有字段可选）。"""
    display_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None


class DefaultModelUpdate(BaseModel):
    """切换默认模型请求。"""
    model: str = Field(min_length=1)
