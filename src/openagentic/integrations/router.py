import asyncio
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.catalog.models import ServiceOffering
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.schemas import BookingResponse
from openagentic.commerce.platform_models import ImportedService, IntegrationDelivery
from openagentic.commerce.platform_schemas import CatalogImport
from openagentic.core.auth.models import User
from openagentic.db.session import get_db
from openagentic.integrations.merchant_api import LocalMerchantAdapter
from openagentic.merchants.router import merchant_user
from openagentic.merchants.service import require_owner

router = APIRouter(tags=["merchant-integrations"])


@router.get("/api/commerce/integrations/example")
async def example_contract():
    return {
        "mode": "local-example",
        "protocol": "openagentic.merchant.v1",
        "catalog": (await LocalMerchantAdapter().catalog()).model_dump(),
    }


@router.post("/api/merchants/{merchant_id}/integrations/catalog")
async def import_catalog(
    merchant_id: UUID,
    body: CatalogImport,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    # Serializes imports by merchant in PostgreSQL, including first-time mappings.
    await require_owner(db, merchant_id, current.id)
    from openagentic.merchants.models import Merchant

    await db.scalar(select(Merchant).where(Merchant.id == merchant_id).with_for_update())
    ids = [item.external_id for item in body.services]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Duplicate external service IDs")
    updated = []
    for incoming in body.services:
        mapping = await db.scalar(
            select(ImportedService).where(
                ImportedService.merchant_id == merchant_id,
                ImportedService.system == body.system,
                ImportedService.external_id == incoming.external_id,
            )
        )
        values = incoming.model_dump(exclude={"external_id"})
        if mapping is None:
            service = ServiceOffering(merchant_id=merchant_id, **values)
            db.add(service)
            await db.flush()
            db.add(
                ImportedService(
                    merchant_id=merchant_id,
                    service_id=service.id,
                    system=body.system,
                    external_id=incoming.external_id,
                )
            )
        else:
            existing_service = await db.scalar(
                select(ServiceOffering).where(
                    ServiceOffering.id == mapping.service_id,
                    ServiceOffering.merchant_id == merchant_id,
                )
            )
            if existing_service is None:
                raise HTTPException(409, "Imported service mapping is inconsistent")
            for key, value in values.items():
                setattr(existing_service, key, value)
            service = existing_service
        updated.append({"external_id": incoming.external_id, "service_id": service.id})
    await db.commit()
    return {"system": body.system, "updated": updated, "count": len(updated)}


@router.get("/api/merchants/{merchant_id}/integrations/deliveries")
async def deliveries(
    merchant_id: UUID, current: User = Depends(merchant_user), db: AsyncSession = Depends(get_db)
):
    await require_owner(db, merchant_id, current.id)
    records = (
        await db.scalars(
            select(IntegrationDelivery)
            .where(
                IntegrationDelivery.merchant_id == merchant_id,
            )
            .order_by(IntegrationDelivery.created_at.desc())
            .limit(100)
        )
    ).all()
    return [delivery_view(item) for item in records]


def delivery_view(item: IntegrationDelivery) -> dict:
    return {
        "id": item.id,
        "order_id": item.order_id,
        "system": item.system,
        "status": item.status,
        "attempts": item.attempts,
        "error": item.error,
        "acknowledgment": item.acknowledgment,
    }


class DeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    system: str = Field(min_length=1, max_length=100)


@router.post("/api/merchants/{merchant_id}/integrations/orders/{order_id}", status_code=201)
async def enqueue_order(
    merchant_id: UUID,
    order_id: UUID,
    body: DeliveryInput,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
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
    if order.status not in {"accepted", "completed"}:
        raise HTTPException(409, "Merchant must accept the order before export")
    record = await db.scalar(
        select(IntegrationDelivery).where(
            IntegrationDelivery.order_id == order.id,
            IntegrationDelivery.system == body.system,
        )
    )
    if record is None:
        record = IntegrationDelivery(
            merchant_id=merchant_id,
            order_id=order.id,
            system=body.system,
            status="pending",
            attempts=0,
            error="",
            acknowledgment={},
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
    return delivery_view(record)


@router.post("/api/merchants/{merchant_id}/integrations/deliveries/{delivery_id}/retry")
async def retry_delivery(
    merchant_id: UUID,
    delivery_id: UUID,
    request: Request,
    current: User = Depends(merchant_user),
    db: AsyncSession = Depends(get_db),
):
    await require_owner(db, merchant_id, current.id)
    record = await db.scalar(
        select(IntegrationDelivery)
        .where(
            IntegrationDelivery.id == delivery_id,
            IntegrationDelivery.merchant_id == merchant_id,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(404, "Integration delivery not found")
    if record.status == "delivered":
        return delivery_view(record)
    if record.attempts >= 10:
        raise HTTPException(409, "Integration retry limit reached")
    adapter = getattr(request.app.state, "merchant_adapters", {}).get(
        (str(merchant_id), record.system)
    )
    if adapter is None and record.system == "local-example":
        adapter = LocalMerchantAdapter()
    if adapter is None:
        raise HTTPException(503, "Merchant adapter not enabled")
    order = await db.get(BookingOrder, record.order_id)
    if order is None or order.status not in {"accepted", "completed"}:
        raise HTTPException(409, "Order is no longer exportable")
    record.attempts += 1
    try:
        result = await asyncio.wait_for(
            adapter.submit_order(BookingResponse.model_validate(order).model_dump(mode="json")),
            timeout=10,
        )
        if (
            not isinstance(result, dict)
            or result.get("order_id") != str(order.id)
            or result.get("status") not in {"pending", "accepted", "completed", "declined"}
        ):
            raise ValueError("Invalid merchant acknowledgment")
        # Acknowledgment is transport evidence, not permission to alter fulfillment.
        record.acknowledgment = {
            key: result[key] for key in ("order_id", "status", "mode") if key in result
        }
        record.status, record.error = "delivered", ""
    except (httpx.HTTPError, TimeoutError, ValueError):
        record.status, record.error = (
            "failed",
            "Merchant delivery failed; retry with the same order ID",
        )
    await db.commit()
    return delivery_view(record)
