from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol


class ConnectorKind(str, enum.Enum):
    CALENDAR = "calendar"
    MAIL = "mail"
    FILES = "files"


@dataclass(frozen=True)
class ConnectorItem:
    id: str
    title: str
    kind: ConnectorKind
    text: str = ""
    start_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class Connector(Protocol):
    kind: ConnectorKind

    async def list(self, query: str = "") -> list[ConnectorItem]: ...


def ensure_within(root: Path, candidate: Path) -> Path:
    root = root.expanduser().resolve()
    path = candidate.expanduser().resolve()
    if path != root and root not in path.parents:
        raise ValueError("connector path escapes workspace")
    return path
