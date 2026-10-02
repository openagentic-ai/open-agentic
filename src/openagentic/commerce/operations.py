import os
from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import Payment, PilotLog, PriceQuote
from openagentic.commerce.platform_schemas import PilotLogInput
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.models import Merchant, MerchantMember
from openagentic.merchants.router import merchant_user
from openagentic.merchants.service import require_owner
from openagentic.merchants.qr import svg

router = APIRouter(tags=["commerce-operations"])


def is_operator(user_id: UUID) -> bool:
    identities = {
        item.strip() for item in os.environ.get("OPENAGENTIC_OPERATOR_IDS", "").split(",")
    }
    return str(user_id) in identities


async def require_operator_or_owner(db: AsyncSession, user: User, merchant_id: UUID) -> None:
    if not is_operator(user.id):
        await require_owner(db, merchant_id, user.id)
    elif await db.get(Merchant, merchant_id) is None:
        raise HTTPException(404, "Merchant not found")


@router.get("/api/merchants/{merchant_id}/share")
async def share_store(
    merchant_id: UUID,
    request: Request,
    origin: str | None = Query(default=None, max_length=100),
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    from urllib.parse import urlsplit

    base = (origin or str(request.base_url)).rstrip("/")
    try:
        parsed = urlsplit(base)
        _ = parsed.port
    except ValueError:
        raise HTTPException(422, "Use a valid website origin") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
    ):
        raise HTTPException(422, "Use a valid website origin")
    url = f"{base}/stores/{merchant_id}"
    try:
        encoded = svg(url)
    except ValueError as exc:
        raise HTTPException(422, "Website address is too long for the QR code") from exc
    return {"url": url, "svg": encoded}


@router.get("/api/commerce/operations")
async def operations(current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)):
    query = select(Merchant)
    operator = is_operator(current.id)
    if not operator:
        query = query.join(MerchantMember, MerchantMember.merchant_id == Merchant.id).where(
            MerchantMember.user_id == current.id,
            MerchantMember.role == "owner",
        )
    stores = list((await db.scalars(query.order_by(Merchant.created_at.desc()))).all())
    mids = [item.id for item in stores]
    orders = list(
        (await db.scalars(select(BookingOrder).where(BookingOrder.merchant_id.in_(mids)))).all()
    )
    logs = list((await db.scalars(select(PilotLog).where(PilotLog.merchant_id.in_(mids)))).all())
    payments = list(
        (
            await db.scalars(
                select(Payment)
                .join(BookingOrder)
                .where(
                    BookingOrder.merchant_id.in_(mids),
                    Payment.provider == "local_simulated",
                )
            )
        ).all()
    )
    quoted = set(
        (
            await db.scalars(
                select(PriceQuote.confirmed_order_id).where(
                    PriceQuote.merchant_id.in_(mids),
                    PriceQuote.confirmed_order_id.is_not(None),
                )
            )
        ).all()
    )
    rows = []
    for store in stores:
        subset = [item for item in orders if item.merchant_id == store.id]
        store_logs = [item for item in logs if item.merchant_id == store.id]
        counts = Counter(item.status for item in subset)
        completed_buyers = Counter(item.buyer_id for item in subset if item.status == "completed")
        attributed = {}
        for log in sorted(store_logs, key=lambda item: item.created_at):
            if log.order_id and log.attribution != "unknown":
                attributed[log.order_id] = log.attribution
        rows.append(
            {
                "id": store.id,
                "name": store.name,
                "region": store.region,
                "orders": len(subset),
                "statuses": dict(counts),
                "repeat_buyers": sum(count >= 2 for count in completed_buyers.values()),
                "quote_confirmed_orders": sum(item.id in quoted for item in subset),
                "founder_minutes": sum(log.minutes for log in store_logs if log.actor == "founder"),
                "team_minutes": sum(log.minutes for log in store_logs if log.actor == "team"),
                "new_platform_orders": sum(
                    value == "new_platform" for value in attributed.values()
                ),
                "existing_customer_orders": sum(
                    value == "existing_customer" for value in attributed.values()
                ),
            }
        )
    paid = [payment for payment in payments if payment.status == "paid"]
    # Cross-merchant evidence uses only authorized stores, never hidden merchants.
    buyers: dict[UUID, set[UUID]] = {}
    for order in orders:
        if order.status == "completed":
            buyers.setdefault(order.buyer_id, set()).add(order.merchant_id)
    return {
        "scope": "platform" if operator else "owned_merchants",
        "merchants": rows,
        "cross_merchant_buyers": sum(len(ids) >= 2 for ids in buyers.values()),
        "payment_mode": "local_simulated",
        "simulated_paid_fen": sum(p.amount_fen for p in paid),
        "simulated_fee_fen": sum(p.fee_fen for p in paid),
    }


@router.post("/api/merchants/{merchant_id}/pilot-logs", status_code=201)
async def add_pilot_log(
    merchant_id: UUID,
    body: PilotLogInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_operator_or_owner(db, current, merchant_id)
    if body.order_id is not None:
        order = await db.scalar(
            select(BookingOrder).where(
                BookingOrder.id == body.order_id,
                BookingOrder.merchant_id == merchant_id,
            )
        )
        if order is None:
            raise HTTPException(404, "Order not found")
    log = PilotLog(merchant_id=merchant_id, user_id=current.id, **body.model_dump())
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return {"id": log.id, "minutes": log.minutes, "actor": log.actor}


@router.get("/api/merchants/{merchant_id}/pilot-logs")
async def pilot_logs(
    merchant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await require_operator_or_owner(db, current, merchant_id)
    logs = (
        await db.scalars(
            select(PilotLog)
            .where(PilotLog.merchant_id == merchant_id)
            .order_by(PilotLog.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "actor": row.actor,
            "category": row.category,
            "minutes": row.minutes,
            "attribution": row.attribution,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in logs
    ]
