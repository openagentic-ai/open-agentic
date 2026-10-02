"""模块说明（中文）：`src/openagentic/core/auth/service.py`。\n\n该文件承载核心业务逻辑，供路由层复用。\n"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.config import SETTINGS
from openagentic.core.auth.models import User

# New hashes support the existing 128-character password contract, including CJK.
# Legacy bcrypt verification bypasses Passlib's incompatible backend probe.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"], pbkdf2_sha256__default_rounds=600_000,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            # Preserve historical bcrypt's 72-byte limit for existing accounts.
            return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("ascii"))
        return pwd_context.verify(plain, hashed)
    except (ValueError, TypeError, UnicodeError):
        return False


def create_access_token(user_id: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=SETTINGS.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, SETTINGS.JWT_SECRET_KEY, algorithm=SETTINGS.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: str) -> str:
    expires_delta = timedelta(days=SETTINGS.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SETTINGS.JWT_SECRET_KEY, algorithm=SETTINGS.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SETTINGS.JWT_SECRET_KEY, algorithms=[SETTINGS.JWT_ALGORITHM])
    except JWTError:
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, display_name: str | None = None) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    return user
