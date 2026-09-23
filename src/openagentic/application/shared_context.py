from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class SharedContext:
    """端适配器传给统一 Agent Application 的最小共享上下文。"""

    user_id: UUID
    session_id: UUID
    task_ids: tuple[UUID, ...] = field(default_factory=tuple)
    endpoint: str = "unknown"
