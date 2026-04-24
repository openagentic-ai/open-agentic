"""模块说明（中文）：`src/openagentic/workflow/runtime.py`。\n\n该文件属于工作流模块，处理定义、执行与状态管理。\n"""

from __future__ import annotations

import asyncio
import uuid


class WorkflowRuntime:
    """Tracks background workflow tasks so they can be cancelled."""

    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    def start(self, run_id: uuid.UUID, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))

    def cancel(self, run_id: uuid.UUID) -> bool:
        task = self._tasks.get(run_id)
        if task is None:
            return False
        task.cancel()
        return True


runtime = WorkflowRuntime()

