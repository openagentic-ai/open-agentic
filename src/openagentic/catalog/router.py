from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.catalog.models import ServiceOffering
from openagentic.catalog.schemas import (
    ServiceInput,
    ServicePublic,
    ServiceResponse,
    StorefrontResponse,
)
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.models import Merchant
from openagentic.merchants.router import merchant_user
from openagentic.merchants.schemas import MerchantPublic
from openagentic.merchants.service import require_owner

router = APIRouter(tags=["catalog"])


@router.get("/api/merchants/{merchant_id}/services", response_model=list[ServiceResponse])
async def list_services(
    merchant_id: UUID,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    return list(
        (
            await db.scalars(
                select(ServiceOffering)
                .where(ServiceOffering.merchant_id == merchant_id)
                .order_by(ServiceOffering.created_at.desc())
            )
        ).all()
    )


@router.post(
    "/api/merchants/{merchant_id}/services", response_model=ServiceResponse, status_code=201
)
async def create_service(
    merchant_id: UUID,
    body: ServiceInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    offering = ServiceOffering(merchant_id=merchant_id, **body.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return offering


@router.put("/api/merchants/{merchant_id}/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    merchant_id: UUID,
    service_id: UUID,
    body: ServiceInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    offering = await db.scalar(
        select(ServiceOffering).where(
            ServiceOffering.id == service_id,
            ServiceOffering.merchant_id == merchant_id,
        )
    )
    if offering is None:
        raise HTTPException(404, "Service not found")
    for key, value in body.model_dump().items():
        setattr(offering, key, value)
    await db.commit()
    await db.refresh(offering)
    return offering


@router.get("/api/catalog/storefronts/{merchant_id}", response_model=StorefrontResponse)
async def get_storefront(merchant_id: UUID, db: AsyncSession = Depends(get_db)):
    merchant = await db.get(Merchant, merchant_id)
    if merchant is None:
        raise HTTPException(404, "Storefront not found")
    offerings = (
        await db.scalars(
            select(ServiceOffering)
            .where(
                ServiceOffering.merchant_id == merchant_id,
                ServiceOffering.is_published.is_(True),
            )
            .order_by(ServiceOffering.created_at.desc())
        )
    ).all()
    return StorefrontResponse(
        merchant=MerchantPublic.model_validate(merchant),
        services=[ServicePublic.model_validate(item) for item in offerings],
    )


@router.get("/api/catalog/services", response_model=list[ServicePublic])
async def discover_services(
    q: str = Query(default="", max_length=100),
    region: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from openagentic.catalog.service import discover_services as query_services

    return await query_services(db=db, q=q, region=region, limit=limit)
