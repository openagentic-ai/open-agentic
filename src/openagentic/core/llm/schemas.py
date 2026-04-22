"""LLM-related schemas."""

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
