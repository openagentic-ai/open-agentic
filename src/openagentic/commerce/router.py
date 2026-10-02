"""HTTP adapter: authenticate, validate input and call appointment services."""

from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from openagentic.commerce import service
from openagentic.commerce.schemas import BookingInput, BookingResponse, BookingStatusInput
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.router import merchant_user

router = APIRouter(tags=["commerce"])


@router.post("/api/orders", response_model=BookingResponse, status_code=201)
async def create_booking(
    body: BookingInput, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    return await service.create_booking(body, current, db)


@router.get("/api/orders", response_model=list[BookingResponse])
async def buyer_orders(current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)):
    return await service.buyer_orders(current, db)


@router.get("/api/orders/{order_id}", response_model=BookingResponse)
async def buyer_order(
    order_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    return await service.buyer_order(order_id, current, db)


@router.post("/api/orders/{order_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    order_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    return await service.cancel_booking(order_id, current, db)


@router.get("/api/merchants/{merchant_id}/orders", response_model=list[BookingResponse])
async def merchant_orders(
    merchant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    return await service.merchant_orders(merchant_id, current, db)


@router.post(
    "/api/merchants/{merchant_id}/orders/{order_id}/status", response_model=BookingResponse
)
async def update_booking_status(
    merchant_id: UUID,
    order_id: UUID,
    body: BookingStatusInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_booking_status(merchant_id, order_id, body, current, db)
