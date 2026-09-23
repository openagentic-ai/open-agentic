import httpx
import pytest

from openagentic.connectors import ConnectorKind, OAuthConfig, OAuthConnector


@pytest.mark.asyncio
async def test_oauth_connector_calls_provider_without_exposing_token():
    seen = {}

    def handler(request: httpx.Request):
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json={"items": [{"id": "e1", "subject": "会议"}]})

    config = OAuthConfig("demo", "client", "https://app/callback", "https://auth", "https://token", "https://api", ("read",))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = OAuthConnector(ConnectorKind.CALENDAR, config, "secret", client)
        items = await connector.list("会议")
    assert items[0].title == "会议"
    assert seen["authorization"] == "Bearer secret"
    assert "secret" not in config.authorization_url("state")
