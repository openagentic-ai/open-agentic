from __future__ import annotations

from uuid import UUID

from openagentic.application.shared_context import SharedContext


class EndpointGateway:
    """把 Web、Android、飞书等入口规范化为同一个应用上下文。"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def context(self, user_id: UUID, session_id: UUID, task_ids: list[UUID] | tuple[UUID, ...] = ()) -> SharedContext:
        return SharedContext(user_id, session_id, tuple(task_ids), self.endpoint)
