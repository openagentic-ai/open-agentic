from openagentic.connectors.base import ConnectorItem, ConnectorKind


class InMemoryConnector:
    """用于本地演示和测试的日历/邮件连接器；外部 OAuth 适配器可复用同一协议。"""

    def __init__(self, kind: ConnectorKind, items: list[ConnectorItem] | None = None):
        if kind is ConnectorKind.FILES:
            raise ValueError("use LocalFileConnector for files")
        self.kind = kind
        self.items = list(items or [])

    async def list(self, query: str = "") -> list[ConnectorItem]:
        needle = query.casefold().strip()
        if not needle:
            return list(self.items)
        return [item for item in self.items if needle in f"{item.title} {item.text}".casefold()]
