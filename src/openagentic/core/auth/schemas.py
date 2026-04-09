"""Auth request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None


class UserLogin(BaseModel):
    email: str  # Also accept username for backward compat with Rust backend
    password: str


class TokenResponse(BaseModel):
    token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str = "Bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
