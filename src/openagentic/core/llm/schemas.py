"""LLM-related schemas."""

from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
