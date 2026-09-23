"""可插拔 OAuth 连接器。

网络客户端通过构造函数注入，生产环境可以接 Google/Microsoft/飞书等服务，
测试和本地部署可以使用 MockTransport，不把 OAuth 凭据写入任务或事件载荷。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from openagentic.connectors.base import ConnectorItem, ConnectorKind


@dataclass(frozen=True)
class OAuthConfig:
    provider: str
    client_id: str
    redirect_uri: str
    authorization_endpoint: str
    token_endpoint: str
    api_base: str
    scopes: tuple[str, ...] = ()

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return str(httpx.URL(self.authorization_endpoint).copy_merge_params(params))


class OAuthConnector:
    def __init__(self, kind: ConnectorKind, config: OAuthConfig, access_token: str, client: httpx.AsyncClient):
        if kind is ConnectorKind.FILES:
            raise ValueError("remote OAuth connector cannot represent files")
        self.kind, self.config, self.access_token, self.client = kind, config, access_token, client

    async def list(self, query: str = "") -> list[ConnectorItem]:
        response = await self.client.get(
            f"{self.config.api_base.rstrip('/')}/items",
            params={"q": query} if query else None,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return [self._item(item) for item in response.json().get("items", [])]

    def _item(self, value: dict[str, Any]) -> ConnectorItem:
        return ConnectorItem(
            id=str(value["id"]),
            title=str(value.get("title") or value.get("subject") or value["id"]),
            kind=self.kind,
            text=str(value.get("text", "")),
            metadata={"provider": self.config.provider},
        )
