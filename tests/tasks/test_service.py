import pytest

from openagentic.tasks.models import TaskStatus
from openagentic.tasks.service import can_transition


def test_task_lifecycle_allows_pause_and_retry():
    assert can_transition(TaskStatus.DRAFT, TaskStatus.PLANNED)
    assert can_transition(TaskStatus.RUNNING, TaskStatus.WAITING_USER)
    assert can_transition(TaskStatus.WAITING_USER, TaskStatus.RUNNING)
    assert can_transition(TaskStatus.FAILED, TaskStatus.PLANNED)


def test_terminal_tasks_cannot_restart():
    assert not can_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING)
    assert not can_transition(TaskStatus.CANCELLED, TaskStatus.PLANNED)
