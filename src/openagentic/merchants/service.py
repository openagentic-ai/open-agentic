from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.merchants.models import Merchant, MerchantMember


async def require_owner(db: AsyncSession, merchant_id: UUID, user_id: UUID) -> Merchant:
    """每次操作按成员关系授权，隐藏其他商家私有资源是否存在。"""
    merchant = await db.scalar(
        select(Merchant).join(MerchantMember, MerchantMember.merchant_id == Merchant.id)
        .where(Merchant.id == merchant_id, MerchantMember.user_id == user_id,
               MerchantMember.role == "owner")
    )
    if merchant is None:
        raise HTTPException(404, "Merchant not found")
    return merchant
