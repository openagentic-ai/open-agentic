"""模块说明（中文）：`src/openagentic/core/llm/schemas.py`。\n\n该文件定义请求/响应数据结构与校验规则。\n"""

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ProviderProfileUpdate(BaseModel):
    display_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None


class DefaultModelUpdate(BaseModel):
    model: str = Field(min_length=1)
