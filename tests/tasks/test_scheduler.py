import asyncio
from uuid import uuid4

import pytest

from openagentic.tasks.scheduler import PersistentTaskScheduler


@pytest.mark.asyncio
async def test_scheduler_reloads_due_tasks_after_start():
    task_id, submitted = uuid4(), []
    async def load_due(_now):
        return [task_id] if not submitted else []
    async def submit(value):
        submitted.append(value)
    scheduler = PersistentTaskScheduler(load_due, submit, interval=0.01)
    runner = asyncio.create_task(scheduler.run())
    await asyncio.wait_for(asyncio.create_task(_wait_for(submitted)), timeout=1)
    scheduler.stop()
    await runner
    assert submitted == [task_id]


async def _wait_for(values):
    while not values:
        await asyncio.sleep(0)
