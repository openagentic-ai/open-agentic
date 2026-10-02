"""Small third-party Agent client. The caller owns transport and credentials.

Inject httpx.ASGITransport for offline use. No implicit network connection,
background task, login, booking confirmation or payment is performed.
"""

import httpx


class CommerceAgentClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def manifest(self) -> dict:
        response = await self.client.get("/api/commerce/tools")
        response.raise_for_status()
        return response.json()

    async def call(self, name: str, arguments: dict) -> dict | list:
        if name not in {"find_services", "quote_service", "get_order"}:
            raise ValueError("Unsupported commercial tool")
        response = await self.client.post(
            f"/api/commerce/tools/{name}", json={"arguments": arguments}
        )
        response.raise_for_status()
        return response.json()

    async def find_services(self, q: str = "", region: str = "") -> list:
        result = await self.call("find_services", {"q": q, "region": region})
        if not isinstance(result, list):
            raise ValueError("Invalid service search response")
        return result

    async def quote_service(self, service_id: str) -> dict:
        result = await self.call("quote_service", {"service_id": service_id})
        if not isinstance(result, dict):
            raise ValueError("Invalid quote response")
        return result

    async def get_order(self, order_id: str) -> dict:
        result = await self.call("get_order", {"order_id": order_id})
        if not isinstance(result, dict):
            raise ValueError("Invalid order response")
        return result
