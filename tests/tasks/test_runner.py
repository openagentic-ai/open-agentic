import asyncio
from uuid import uuid4

import pytest

from openagentic.tasks.runner import TaskRunner


@pytest.mark.asyncio
async def test_runner_pause_and_resume_is_cooperative():
    runner = TaskRunner()
    task_id = uuid4()
    started = asyncio.Event()
    progressed = asyncio.Event()

    async def job(resume_event: asyncio.Event):
        started.set()
        await asyncio.sleep(0)
        await resume_event.wait()
        progressed.set()

    runner.submit(task_id, job)
    await started.wait()
    runner.pause(task_id)
    await asyncio.sleep(0)
    assert not progressed.is_set()
    runner.resume(task_id)
    await asyncio.wait_for(progressed.wait(), timeout=1)
