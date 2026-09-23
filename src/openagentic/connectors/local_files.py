from __future__ import annotations

from pathlib import Path

from openagentic.connectors.base import ConnectorItem, ConnectorKind, ensure_within


class LocalFileConnector:
    """只读本地工作区文件连接器，默认不允许越过工作区根目录。"""

    kind = ConnectorKind.FILES

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def list(self, query: str = "") -> list[ConnectorItem]:
        needle = query.casefold().strip()
        items: list[ConnectorItem] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or (needle and needle not in path.name.casefold()):
                continue
            safe = ensure_within(self.root, path)
            items.append(
                ConnectorItem(
                    id=str(safe.relative_to(self.root)),
                    title=safe.name,
                    kind=self.kind,
                    metadata={"path": str(safe)},
                )
            )
        return items
