from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.merchants.models import Merchant, MerchantMember
from openagentic.merchants.schemas import MerchantInput, MerchantResponse
from openagentic.merchants.service import require_owner

router = APIRouter(prefix="/api/merchants", tags=["merchants"])


async def merchant_user(current: User = Depends(get_current_user)) -> User:
    if not current.is_active:
        raise HTTPException(403, "Account is inactive")
    return current


@router.post("", response_model=MerchantResponse, status_code=201)
async def create_merchant(
    body: MerchantInput, current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    merchant = Merchant(**body.model_dump())
    db.add(merchant)
    await db.flush()
    db.add(MerchantMember(merchant_id=merchant.id, user_id=current.id, role="owner"))
    await db.commit()
    await db.refresh(merchant)
    return merchant


@router.get("", response_model=list[MerchantResponse])
async def list_merchants(
    current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db),
):
    query = select(Merchant).join(MerchantMember, MerchantMember.merchant_id == Merchant.id)
    query = query.where(MerchantMember.user_id == current.id, MerchantMember.role == "owner")
    return list((await db.scalars(query.order_by(Merchant.created_at.desc()))).all())


@router.get("/{merchant_id}", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: UUID, current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    return await require_owner(db, merchant_id, current.id)


@router.put("/{merchant_id}", response_model=MerchantResponse)
async def update_merchant(
    merchant_id: UUID, body: MerchantInput, current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    merchant = await require_owner(db, merchant_id, current.id)
    for key, value in body.model_dump().items():
        setattr(merchant, key, value)
    await db.commit()
    await db.refresh(merchant)
    return merchant
