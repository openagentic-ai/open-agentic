import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.commerce.access import CommerceActor, get_commerce_actor, utc
from openagentic.commerce.agent_tools import CommerceTools
from openagentic.commerce.platform_models import AgentGrant, PriceQuote, ToolAudit
from openagentic.commerce.platform_schemas import (
    GrantInput,
    QuoteConfirmation,
    QuoteResponse,
    ToolCall,
)
from openagentic.commerce.quotes import confirm_quote
from openagentic.commerce.schemas import BookingResponse
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.router import merchant_user

router = APIRouter(prefix="/api/commerce", tags=["commerce-agents"])


@router.get("/tools")
async def tools_manifest(
    actor: CommerceActor = Depends(get_commerce_actor), db: AsyncSession = Depends(get_db)
):
    return {
        "protocol": "openagentic.commerce.v1",
        "tools": CommerceTools(db, actor).registry.litellm_schema_for("commerce"),
        "booking_confirmation": "user_session_required",
        "external_network": "disabled_by_default",
    }


@router.post("/tools/{name}")
async def call_tool(
    name: str,
    body: ToolCall,
    actor: CommerceActor = Depends(get_commerce_actor),
    db: AsyncSession = Depends(get_db),
):
    return await CommerceTools(db, actor).execute(name, body.arguments)


@router.post("/agent-grants", status_code=201)
async def create_grant(
    body: GrantInput, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    token = "oa_agent_" + secrets.token_urlsafe(32)
    grant = AgentGrant(
        user_id=current.id,
        name=body.name,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        scopes=sorted(set(body.scopes)),
        revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_days),
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return {
        "id": grant.id,
        "token": token,
        "name": grant.name,
        "scopes": grant.scopes,
        "expires_at": utc(grant.expires_at),
    }


@router.get("/agent-grants")
async def list_grants(current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)):
    grants = (
        await db.scalars(
            select(AgentGrant)
            .where(AgentGrant.user_id == current.id)
            .order_by(AgentGrant.created_at.desc())
        )
    ).all()
    return [
        {
            "id": grant.id,
            "name": grant.name,
            "scopes": grant.scopes,
            "expires_at": utc(grant.expires_at),
            "revoked": grant.revoked,
        }
        for grant in grants
    ]


@router.delete("/agent-grants/{grant_id}")
async def revoke_grant(
    grant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    grant = await db.scalar(
        select(AgentGrant).where(AgentGrant.id == grant_id, AgentGrant.user_id == current.id)
    )
    if grant is None:
        raise HTTPException(404, "Agent grant not found")
    grant.revoked = True
    await db.commit()
    return {"revoked": grant.id}


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
async def read_quote(
    quote_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    quote = await db.scalar(
        select(PriceQuote).where(PriceQuote.id == quote_id, PriceQuote.buyer_id == current.id)
    )
    if quote is None:
        raise HTTPException(404, "Quote not found")
    return quote


@router.post("/quotes/{quote_id}/confirm", response_model=BookingResponse)
async def user_confirms_quote(
    quote_id: UUID,
    body: QuoteConfirmation,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_quote(db, current, quote_id, body)


@router.get("/tool-audits")
async def tool_audits(current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)):
    records = (
        await db.scalars(
            select(ToolAudit)
            .where(ToolAudit.user_id == current.id)
            .order_by(ToolAudit.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": row.id,
            "tool_name": row.tool_name,
            "success": row.success,
            "status_code": row.status_code,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
        }
        for row in records
    ]
