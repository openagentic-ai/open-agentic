"""模块说明（中文）：`src/openagentic/core/auth/router.py`。\n\n该文件定义 HTTP 路由与请求入口，负责参数校验与服务层调用。\n"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.db.session import get_db
from openagentic.core.auth import schemas, service
from openagentic.deps import get_current_user
from openagentic.core.auth.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: schemas.UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await service.create_user(db, body.email, body.password, body.display_name)
    token, expires_in = service.create_access_token(str(user.id))
    refresh_token = service.create_refresh_token(str(user.id))
    return schemas.TokenResponse(token=token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/login", response_model=schemas.TokenResponse)
async def login(body: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, body.email)
    if not user or not service.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token, expires_in = service.create_access_token(str(user.id))
    refresh_token = service.create_refresh_token(str(user.id))
    return schemas.TokenResponse(token=token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", response_model=schemas.TokenResponse)
async def refresh(token: str, db: AsyncSession = Depends(get_db)):
    payload = service.decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_token, expires_in = service.create_access_token(payload["sub"])
    new_refresh = service.create_refresh_token(payload["sub"])
    return schemas.TokenResponse(token=new_token, refresh_token=new_refresh, expires_in=expires_in)


@router.get("/me", response_model=schemas.UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
