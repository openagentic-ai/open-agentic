"""DefaultSessionStore——SessionStore 内存实现。

按 (adapter_id, external_session_id) 索引；session_id 用 UUID4。

Phase 1 内存版足够单机 / 单进程运行；多进程或重启持久化由 Phase 4+ 的 DB 实现接管。

参考: docs/ADR-001-multi-adapter-foundation.md §5
"""
from __future__ import annotations

import asyncio
import uuid

from openagentic.application.session import Session


class DefaultSessionStore:
    """内存版 SessionStore。线程安全(单 asyncio.Lock 串行化写)。"""

    def __init__(self) -> None:
        self._by_id: dict[str, Session] = {}
        self._by_external: dict[tuple[str, str], str] = {}   # (adapter_id, ext_id) -> session_id
        self._by_user: dict[str, set[str]] = {}              # user_id -> {session_id}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self, adapter_id: str, external_session_id: str, user_id: str
    ) -> Session:
        key = (adapter_id, external_session_id)
        async with self._lock:
            sid = self._by_external.get(key)
            if sid is not None:
                return self._by_id[sid]
            sid = str(uuid.uuid4())
            session = Session(
                session_id=sid,
                adapter_id=adapter_id,
                external_session_id=external_session_id,
                user_id=user_id,
            )
            self._by_id[sid] = session
            self._by_external[key] = sid
            self._by_user.setdefault(user_id, set()).add(sid)
            return session

    async def get_by_id(self, session_id: str) -> Session | None:
        return self._by_id.get(session_id)

    async def list_by_user(self, user_id: str) -> list[Session]:
        sids = self._by_user.get(user_id, set())
        return [self._by_id[sid] for sid in sids if sid in self._by_id]


__all__ = ["DefaultSessionStore"]
