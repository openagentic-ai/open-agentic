import pytest

from openagentic.connectors import ConnectorItem, ConnectorKind, InMemoryConnector


@pytest.mark.asyncio
async def test_calendar_and_mail_share_connector_contract():
    connector = InMemoryConnector(
        ConnectorKind.MAIL,
        [ConnectorItem("m1", "验收邮件", ConnectorKind.MAIL, text="周五")],
    )
    assert [item.id for item in await connector.list("周五")] == ["m1"]
