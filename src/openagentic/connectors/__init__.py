"""个人助手连接器协议与本地可用实现。"""

from openagentic.connectors.base import Connector, ConnectorItem, ConnectorKind
from openagentic.connectors.local_files import LocalFileConnector
from openagentic.connectors.memory import InMemoryConnector

__all__ = ["Connector", "ConnectorItem", "ConnectorKind", "LocalFileConnector", "InMemoryConnector"]
