from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.commerce.finance_router import accessible_order
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import SupportCase
from openagentic.commerce.platform_schemas import CaseInput, CaseResolution
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.merchants.router import merchant_user
from openagentic.merchants.service import require_owner

router = APIRouter(tags=["commerce-support"])


def case_view(case: SupportCase) -> dict:
    return {
        "id": case.id,
        "order_id": case.order_id,
        "subject": case.subject,
        "description": case.description,
        "status": case.status,
        "resolution": case.resolution,
    }


@router.post("/api/orders/{order_id}/cases", status_code=201)
async def open_case(
    order_id: UUID,
    body: CaseInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.scalar(
        select(BookingOrder).where(BookingOrder.id == order_id, BookingOrder.buyer_id == current.id)
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    case = SupportCase(
        order_id=order.id, buyer_id=current.id, **body.model_dump(), status="open", resolution=""
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case_view(case)


@router.get("/api/orders/{order_id}/cases")
async def order_cases(
    order_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await accessible_order(db, current, order_id)
    cases = (
        await db.scalars(
            select(SupportCase)
            .where(SupportCase.order_id == order_id)
            .order_by(SupportCase.created_at.desc())
        )
    ).all()
    return [case_view(case) for case in cases]


@router.post("/api/merchants/{merchant_id}/cases/{case_id}/resolve")
async def resolve_case(
    merchant_id: UUID,
    case_id: UUID,
    body: CaseResolution,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    case = await db.scalar(
        select(SupportCase)
        .join(BookingOrder)
        .where(
            SupportCase.id == case_id,
            BookingOrder.merchant_id == merchant_id,
        )
        .with_for_update(of=SupportCase)
    )
    if case is None:
        raise HTTPException(404, "Support case not found")
    if case.status == "closed":
        raise HTTPException(409, "Support case already closed")
    case.status, case.resolution = "resolved", body.resolution
    await db.commit()
    return case_view(case)


@router.post("/api/commerce/cases/{case_id}/close")
async def close_case(
    case_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    case = await db.scalar(
        select(SupportCase)
        .where(SupportCase.id == case_id, SupportCase.buyer_id == current.id)
        .with_for_update()
    )
    if case is None:
        raise HTTPException(404, "Support case not found")
    if case.status not in {"resolved", "closed"}:
        raise HTTPException(409, "Support case has no resolution yet")
    case.status = "closed"
    await db.commit()
    return case_view(case)
