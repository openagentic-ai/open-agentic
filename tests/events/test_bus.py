import pytest

from openagentic.events import Event, EventBus


@pytest.mark.asyncio
async def test_event_bus_dispatches_user_scoped_events():
    bus = EventBus()
    received = []
    bus.subscribe("task.updated", lambda event: _receive(received, event))
    await bus.publish(Event("task.updated", "u1", {"task_id": "t1"}))
    assert received[0].user_id == "u1"


async def _receive(received, event):
    received.append(event)
