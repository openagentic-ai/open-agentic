from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.commerce.models import BookingOrder
from openagentic.commerce.operations import is_operator, require_operator_or_owner
from openagentic.commerce.platform_models import FeePolicy, Payment, Refund
from openagentic.commerce.platform_schemas import (
    FeeInput,
    PaymentInput,
    RefundInput,
    RefundResolution,
)
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.router import merchant_user
from openagentic.merchants.service import require_owner
from openagentic.merchants.models import Merchant

router = APIRouter(tags=["commerce-finance"])


def payment_view(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "provider": payment.provider,
        "amount_fen": payment.amount_fen,
        "fee_fen": payment.fee_fen,
        "merchant_net_fen": payment.amount_fen - payment.fee_fen,
        "status": payment.status,
    }


def refund_view(refund: Refund) -> dict:
    return {
        "id": refund.id,
        "payment_id": refund.payment_id,
        "reason": refund.reason,
        "status": refund.status,
        "resolution": refund.resolution,
    }


async def accessible_order(db: AsyncSession, user: User, order_id: UUID) -> BookingOrder:
    order = await db.get(BookingOrder, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    if order.buyer_id != user.id:
        await require_operator_or_owner(db, user, order.merchant_id)
    return order


def local_provider(request: Request):
    provider = getattr(request.app.state, "payment_provider", None)
    if provider is None or provider.mode != "local_simulated":
        raise HTTPException(503, "Payment provider not enabled")
    return provider


@router.get("/api/commerce/payments/capabilities")
async def payment_capabilities(request: Request):
    provider = getattr(request.app.state, "payment_provider", None)
    return {"mode": provider.mode if provider else "disabled", "real_money": False}


@router.post("/api/orders/{order_id}/payments", status_code=201)
async def pay_order(
    order_id: UUID,
    body: PaymentInput,
    request: Request,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    provider = local_provider(request)
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
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if payment is not None:
        if payment.request_id != body.request_id:
            raise HTTPException(409, "This order already has a payment")
        return payment_view(payment)
    if order.status != "accepted":
        raise HTTPException(409, "Merchant must accept the order before payment")
    policy = await db.scalar(select(FeePolicy).where(FeePolicy.merchant_id == order.merchant_id))
    fee = (
        min(order.price_fen, (order.price_fen * policy.basis_points // 10000 + policy.flat_fen))
        if policy
        else 0
    )
    payment = Payment(
        order_id=order.id,
        request_id=body.request_id,
        provider=provider.mode,
        provider_reference=provider.pay(order.id, order.price_fen),
        amount_fen=order.price_fen,
        fee_fen=fee,
        status="paid",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment_view(payment)


@router.get("/api/orders/{order_id}/finance")
async def order_finance(
    order_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await accessible_order(db, current, order_id)
    payment = await db.scalar(select(Payment).where(Payment.order_id == order_id))
    refund = (
        await db.scalar(select(Refund).where(Refund.payment_id == payment.id)) if payment else None
    )
    return {
        "payment": payment_view(payment) if payment else None,
        "refund": refund_view(refund) if refund else None,
    }


@router.post("/api/orders/{order_id}/refunds", status_code=201)
async def request_refund(
    order_id: UUID,
    body: RefundInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
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
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if payment is None:
        raise HTTPException(409, "No paid payment to refund")
    existing = await db.scalar(select(Refund).where(Refund.payment_id == payment.id))
    if existing:
        return refund_view(existing)
    if payment.status != "paid":
        raise HTTPException(409, "Payment already refunded")
    refund = Refund(
        payment_id=payment.id,
        buyer_id=current.id,
        reason=body.reason,
        status="requested",
        resolution="",
    )
    db.add(refund)
    await db.commit()
    await db.refresh(refund)
    return refund_view(refund)


@router.post("/api/merchants/{merchant_id}/refunds/{refund_id}/resolve")
async def resolve_refund(
    merchant_id: UUID,
    refund_id: UUID,
    body: RefundResolution,
    request: Request,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    refund = await db.scalar(
        select(Refund)
        .join(Payment)
        .join(BookingOrder)
        .where(
            Refund.id == refund_id,
            BookingOrder.merchant_id == merchant_id,
        )
        .with_for_update(of=Refund)
    )
    if refund is None:
        raise HTTPException(404, "Refund not found")
    target = "processed" if body.approve else "declined"
    if refund.status == target:
        return refund_view(refund)
    if refund.status != "requested":
        raise HTTPException(409, "Refund already resolved")
    payment = await db.get(Payment, refund.payment_id)
    if payment is None:
        raise HTTPException(409, "Payment not found")
    if body.approve:
        local_provider(request).refund(payment.provider_reference, payment.amount_fen)
        payment.status = "refunded"
    refund.status, refund.resolution = target, body.resolution
    await db.commit()
    return refund_view(refund)


@router.get("/api/merchants/{merchant_id}/fee-policy")
async def read_fee(
    merchant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await require_operator_or_owner(db, current, merchant_id)
    policy = await db.scalar(select(FeePolicy).where(FeePolicy.merchant_id == merchant_id))
    return {
        "basis_points": policy.basis_points if policy else 0,
        "flat_fen": policy.flat_fen if policy else 0,
        "can_edit": is_operator(current.id),
        "mode": "local_simulated",
    }


@router.put("/api/merchants/{merchant_id}/fee-policy")
async def set_fee(
    merchant_id: UUID,
    body: FeeInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    if not is_operator(current.id):
        raise HTTPException(403, "Platform operator required")
    await require_operator_or_owner(db, current, merchant_id)
    await db.scalar(select(Merchant).where(Merchant.id == merchant_id).with_for_update())
    policy = await db.scalar(
        select(FeePolicy).where(FeePolicy.merchant_id == merchant_id).with_for_update()
    )
    if policy is None:
        policy = FeePolicy(merchant_id=merchant_id, **body.model_dump())
        db.add(policy)
    else:
        policy.basis_points, policy.flat_fen = body.basis_points, body.flat_fen
    await db.commit()
    return {**body.model_dump(), "mode": "local_simulated"}


@router.get("/api/merchants/{merchant_id}/billing")
async def merchant_billing(
    merchant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await require_operator_or_owner(db, current, merchant_id)
    payments = (
        await db.scalars(
            select(Payment)
            .join(BookingOrder)
            .where(
                BookingOrder.merchant_id == merchant_id,
                Payment.provider == "local_simulated",
            )
            .order_by(Payment.created_at.desc())
        )
    ).all()
    paid = [item for item in payments if item.status == "paid"]
    return {
        "mode": "local_simulated",
        "payments": [payment_view(item) for item in payments],
        "paid_fen": sum(item.amount_fen for item in paid),
        "fee_fen": sum(item.fee_fen for item in paid),
        "net_fen": sum(item.amount_fen - item.fee_fen for item in paid),
        "refunded_fen": sum(item.amount_fen for item in payments if item.status == "refunded"),
    }
