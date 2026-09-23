from openagentic.tasks.models import Task, TaskStatus


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.PLANNED, TaskStatus.CANCELLED}),
    TaskStatus.PLANNED: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset(
        {TaskStatus.WAITING_USER, TaskStatus.BLOCKED, TaskStatus.COMPLETED, TaskStatus.FAILED}
    ),
    TaskStatus.WAITING_USER: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.PLANNED, TaskStatus.CANCELLED}),
    TaskStatus.FAILED: frozenset({TaskStatus.PLANNED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return current == target or target in _ALLOWED_TRANSITIONS[current]


def transition(task: Task, target: TaskStatus) -> Task:
    if not can_transition(task.status, target):
        raise ValueError(f"invalid task transition: {task.status.value} -> {target.value}")
    task.status = target
    return task
