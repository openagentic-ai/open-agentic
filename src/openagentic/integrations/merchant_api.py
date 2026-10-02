from typing import Protocol

import httpx

from openagentic.commerce.platform_schemas import CatalogImport


class MerchantAdapter(Protocol):
    async def catalog(self) -> CatalogImport: ...
    async def submit_order(self, order: dict) -> dict: ...


class HttpMerchantAdapter:
    """Adapter for the OpenAgentic merchant contract, not a specific SaaS vendor.

    The deployment supplies the authenticated client and base URL. Construction
    performs no I/O; tests use MockTransport. No automatic polling is scheduled.
    """

    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client, self.base_url = client, base_url.rstrip("/")

    async def catalog(self) -> CatalogImport:
        response = await self.client.get(f"{self.base_url}/catalog", timeout=10)
        response.raise_for_status()
        return CatalogImport.model_validate(response.json())

    async def submit_order(self, order: dict) -> dict:
        response = await self.client.post(
            f"{self.base_url}/orders",
            json=order,
            headers={"Idempotency-Key": str(order["id"])},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or body.get("order_id") != str(order["id"]):
            raise ValueError("Merchant system returned an unrelated order")
        return body


class LocalMerchantAdapter:
    """Explicitly simulated merchant system for offline contract verification."""

    async def catalog(self) -> CatalogImport:
        return CatalogImport.model_validate(
            {
                "system": "local-example",
                "services": [
                    {
                        "external_id": "cleaning-001",
                        "name": "示例空调清洗",
                        "description": "本地示例系统",
                        "price_fen": 9800,
                        "duration_minutes": 60,
                        "availability_note": "时间需商家确认",
                        "is_published": False,
                    }
                ],
            }
        )

    async def submit_order(self, order: dict) -> dict:
        return {"order_id": str(order["id"]), "status": "pending", "mode": "local-example"}
