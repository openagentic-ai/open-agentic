"""模块说明（中文）：`src/openagentic/core/auth/router.py`。

认证 HTTP API 路由：注册、登录、Token 刷新、当前用户查询。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.db.session import get_db
from openagentic.core.auth import schemas, service
from openagentic.deps import get_current_user
from openagentic.core.auth.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: schemas.UserRegister, db: AsyncSession = Depends(get_db)):
    """注册新用户：检查邮箱唯一性 → 创建用户 → 返回 JWT 对。"""
    existing = await service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await service.create_user(db, body.email, body.password, body.display_name)
    token, expires_in = service.create_access_token(str(user.id))
    refresh_token = service.create_refresh_token(str(user.id))
    return schemas.TokenResponse(token=token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/login", response_model=schemas.TokenResponse)
async def login(body: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录：验证邮箱+密码 → 返回 JWT 对。"""
    user = await service.get_user_by_email(db, body.email)
    if not user or not service.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token, expires_in = service.create_access_token(str(user.id))
    refresh_token = service.create_refresh_token(str(user.id))
    return schemas.TokenResponse(token=token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh(token: str, db: AsyncSession = Depends(get_db)):
    """刷新 Access Token（使用 refresh token 换新的 JWT 对）。"""
    payload = service.decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_token, expires_in = service.create_access_token(payload["sub"])
    new_refresh = service.create_refresh_token(payload["sub"])
    return schemas.TokenResponse(token=new_token, refresh_token=new_refresh, expires_in=expires_in)


@router.get("/me", response_model=schemas.UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return current_user
