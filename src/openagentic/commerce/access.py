import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.commerce.platform_models import AgentGrant
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.deps import get_current_user, security


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class CommerceActor:
    user: User
    grant: AgentGrant | None = None

    def require(self, scope: str) -> None:
        if self.grant is not None and scope not in self.grant.scopes:
            raise HTTPException(403, "Agent permission denied")


async def get_commerce_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CommerceActor:
    if credentials and credentials.credentials.startswith("oa_agent_"):
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        grant = await db.scalar(select(AgentGrant).where(AgentGrant.token_hash == digest))
        if grant is None or grant.revoked or utc(grant.expires_at) <= datetime.now(timezone.utc):
            raise HTTPException(401, "Invalid Agent access token")
        user = await db.get(User, grant.user_id)
        if user is None or not user.is_active:
            raise HTTPException(403, "Account is inactive")
        return CommerceActor(user, grant)
    user = await get_current_user(credentials=credentials, db=db)
    if not user.is_active:
        raise HTTPException(403, "Account is inactive")
    return CommerceActor(user)
