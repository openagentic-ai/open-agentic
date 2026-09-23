from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID


class PersistentTaskScheduler:
    """用持久化任务查询函数驱动后台执行；进程重启后从数据库再次加载到期任务。"""

    def __init__(self, load_due: Callable[[datetime], Awaitable[list[UUID]]], submit: Callable[[UUID], Awaitable[None]], interval: float = 5.0):
        self.load_due, self.submit, self.interval = load_due, submit, interval
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            for task_id in await self.load_due(datetime.now(timezone.utc)):
                await self.submit(task_id)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
