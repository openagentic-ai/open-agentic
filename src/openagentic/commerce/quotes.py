from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.catalog.models import ServiceOffering
from openagentic.commerce.access import CommerceActor, utc
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import PriceQuote
from openagentic.commerce.platform_schemas import QuoteConfirmation
from openagentic.commerce.service import create_booking
from openagentic.commerce.schemas import BookingInput
from openagentic.core.auth.models import User


async def create_quote(db: AsyncSession, actor: CommerceActor, service_id: UUID) -> PriceQuote:
    actor.require("quotes:write")
    offering = await db.scalar(
        select(ServiceOffering).where(
            ServiceOffering.id == service_id,
            ServiceOffering.is_published.is_(True),
        )
    )
    if offering is None:
        raise HTTPException(404, "Published service not found")
    quote = PriceQuote(
        buyer_id=actor.user.id,
        service_id=offering.id,
        merchant_id=offering.merchant_id,
        grant_id=actor.grant.id if actor.grant else None,
        service_name=offering.name,
        price_fen=offering.price_fen,
        duration_minutes=offering.duration_minutes,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return quote


async def confirm_quote(
    db: AsyncSession,
    user: User,
    quote_id: UUID,
    body: QuoteConfirmation,
) -> BookingOrder:
    quote = await db.scalar(
        select(PriceQuote)
        .where(
            PriceQuote.id == quote_id,
            PriceQuote.buyer_id == user.id,
        )
        .with_for_update()
    )
    if quote is None:
        raise HTTPException(404, "Quote not found")
    existing = await db.scalar(
        select(BookingOrder).where(
            BookingOrder.buyer_id == user.id,
            BookingOrder.request_id == quote.id,
        )
    )
    if existing is None and utc(quote.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Quote expired; request a new quote")
    if existing is None:
        offering = await db.scalar(
            select(ServiceOffering)
            .where(
                ServiceOffering.id == quote.service_id,
                ServiceOffering.is_published.is_(True),
            )
            .with_for_update()
        )
        if offering is None:
            raise HTTPException(404, "Published service not found")
        if (offering.name, offering.price_fen, offering.duration_minutes) != (
            quote.service_name,
            quote.price_fen,
            quote.duration_minutes,
        ):
            raise HTTPException(409, "Service changed; request a new quote")
    order = await create_booking(
        BookingInput(
            service_id=quote.service_id,
            request_id=quote.id,
            expected_price_fen=quote.price_fen,
            **body.model_dump(),
        ),
        current=user,
        db=db,
    )
    # If a crash occurs between commits, retry recovers by the quote's unique request ID.
    quote.confirmed_order_id = order.id
    await db.commit()
    return order
