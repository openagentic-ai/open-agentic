"""模块说明（中文）：`src/openagentic/core/auth/schemas.py`。

认证模块请求/响应数据结构（Pydantic models）。
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """用户注册请求。密码长度 6-128。"""
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None


class UserLogin(BaseModel):
    """用户登录请求。email 字段兼容用户名输入（为 Rust 后端兼容）。"""
    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT Token 响应：access token + refresh token + 过期时间。"""
    token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str = "Bearer"


class UserResponse(BaseModel):
    """用户信息响应。"""
    id: uuid.UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
