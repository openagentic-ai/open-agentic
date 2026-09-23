"""进程内后台任务协调器。

任务状态仍由数据库保存；协调器只负责当前进程中的执行句柄，重启后可由
`next_run_at` 重新调度。这让暂停/恢复成为显式、可测试的协作协议。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID


Job = Callable[[asyncio.Event], Awaitable[None]]


class TaskRunner:
    def __init__(self) -> None:
        self._jobs: dict[UUID, asyncio.Task[None]] = {}
        self._resume_events: dict[UUID, asyncio.Event] = {}

    def submit(self, task_id: UUID, job: Job) -> asyncio.Task[None]:
        if task_id in self._jobs and not self._jobs[task_id].done():
            raise ValueError(f"task already running: {task_id}")
        event = asyncio.Event()
        event.set()
        self._resume_events[task_id] = event

        async def wrapped() -> None:
            try:
                await job(event)
            finally:
                self._jobs.pop(task_id, None)
                self._resume_events.pop(task_id, None)

        handle = asyncio.create_task(wrapped(), name=f"openagentic-task-{task_id}")
        self._jobs[task_id] = handle
        return handle

    def pause(self, task_id: UUID) -> None:
        event = self._resume_events.get(task_id)
        if event is None:
            raise KeyError(task_id)
        event.clear()

    def resume(self, task_id: UUID) -> None:
        event = self._resume_events.get(task_id)
        if event is None:
            raise KeyError(task_id)
        event.set()

    def cancel(self, task_id: UUID) -> None:
        handle = self._jobs.get(task_id)
        if handle is not None:
            handle.cancel()

    def get(self, task_id: UUID) -> asyncio.Task[None] | None:
        return self._jobs.get(task_id)


default_runner = TaskRunner()
