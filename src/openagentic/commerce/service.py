"""Appointment business rules shared by REST and Agent application adapters."""

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.catalog.models import ServiceOffering
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import Payment
from openagentic.commerce.schemas import BookingInput, BookingStatusInput
from openagentic.core.auth.models import User
from openagentic.merchants.service import require_owner


def _replay(order: BookingOrder, fingerprint: str) -> BookingOrder:
    if order.request_fingerprint != fingerprint:
        raise HTTPException(409, "Request ID already used for another booking")
    return order


async def create_booking(
    body: BookingInput,
    current: User,
    db: AsyncSession,
):
    payload = body.model_dump(mode="json")
    payload["preferred_at"] = body.preferred_at.astimezone(timezone.utc).isoformat()
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    replay_query = select(BookingOrder).where(
        BookingOrder.buyer_id == current.id,
        BookingOrder.request_id == body.request_id,
    )
    existing = await db.scalar(replay_query)
    if existing is not None:
        return _replay(existing, fingerprint)
    if body.preferred_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "Please choose a future time")
    # Lock the offering while creating its price snapshot; concurrent updates serialize.
    offering = await db.scalar(
        select(ServiceOffering)
        .where(
            ServiceOffering.id == body.service_id,
            ServiceOffering.is_published.is_(True),
        )
        .with_for_update()
    )
    if offering is None:
        raise HTTPException(404, "Published service not found")
    if offering.price_fen != body.expected_price_fen:
        raise HTTPException(409, "Service price changed; review it before confirming")
    order = BookingOrder(
        buyer_id=current.id,
        merchant_id=offering.merchant_id,
        service_id=offering.id,
        request_id=body.request_id,
        request_fingerprint=fingerprint,
        service_name=offering.name,
        price_fen=offering.price_fen,
        duration_minutes=offering.duration_minutes,
        preferred_at=body.preferred_at.astimezone(timezone.utc),
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        note=body.note,
        status="pending",
    )
    db.add(order)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(replay_query)
        if existing is None:
            raise
        return _replay(existing, fingerprint)
    await db.refresh(order)
    return order


async def buyer_orders(
    current: User,
    db: AsyncSession,
):
    return list(
        (
            await db.scalars(
                select(BookingOrder)
                .where(
                    BookingOrder.buyer_id == current.id,
                )
                .order_by(BookingOrder.created_at.desc())
            )
        ).all()
    )


async def buyer_order(
    order_id: UUID,
    current: User,
    db: AsyncSession,
):
    order = await db.scalar(
        select(BookingOrder).where(
            BookingOrder.id == order_id,
            BookingOrder.buyer_id == current.id,
        )
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


async def cancel_booking(
    order_id: UUID,
    current: User,
    db: AsyncSession,
):
    order = await db.scalar(
        select(BookingOrder)
        .where(
            BookingOrder.id == order_id,
            BookingOrder.buyer_id == current.id,
        )
        .with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    if order.status == "cancelled":
        return order
    if order.status not in {"pending", "accepted"}:
        raise HTTPException(409, "Order cannot be cancelled in its current status")
    paid = await db.scalar(
        select(Payment).where(Payment.order_id == order.id, Payment.status == "paid")
    )
    if paid is not None:
        raise HTTPException(409, "Request a refund before cancelling a paid order")
    order.status = "cancelled"
    await db.commit()
    await db.refresh(order)
    return order


async def merchant_orders(
    merchant_id: UUID,
    current: User,
    db: AsyncSession,
):
    await require_owner(db, merchant_id, current.id)
    return list(
        (
            await db.scalars(
                select(BookingOrder)
                .where(
                    BookingOrder.merchant_id == merchant_id,
                )
                .order_by(BookingOrder.created_at.desc())
            )
        ).all()
    )


async def update_booking_status(
    merchant_id: UUID,
    order_id: UUID,
    body: BookingStatusInput,
    current: User,
    db: AsyncSession,
):
    await require_owner(db, merchant_id, current.id)
    order = await db.scalar(
        select(BookingOrder)
        .where(
            BookingOrder.id == order_id,
            BookingOrder.merchant_id == merchant_id,
        )
        .with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    allowed = {"pending": {"accepted", "declined"}, "accepted": {"completed"}}
    if order.status != body.status and body.status not in allowed.get(order.status, set()):
        raise HTTPException(409, "Invalid order status transition")
    order.status = body.status
    await db.commit()
    await db.refresh(order)
    return order
