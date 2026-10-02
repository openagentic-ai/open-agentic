"""Published catalog query used by HTTP and Agent tools."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openagentic.catalog.models import ServiceOffering
from openagentic.merchants.models import Merchant


async def discover_services(
    *, db: AsyncSession, q: str = "", region: str = "", limit: int = 50
) -> list[ServiceOffering]:
    query = select(ServiceOffering).join(Merchant).where(ServiceOffering.is_published.is_(True))
    if q.strip():
        query = query.where(ServiceOffering.name.contains(q.strip(), autoescape=True))
    if region.strip():
        query = query.where(Merchant.region == region.strip())
    return list(
        (await db.scalars(query.order_by(ServiceOffering.created_at.desc()).limit(limit))).all()
    )
