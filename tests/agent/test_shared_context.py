from uuid import uuid4

from openagentic.application.shared_context import SharedContext


def test_endpoints_share_identity_session_and_tasks():
    user, session, task = uuid4(), uuid4(), uuid4()
    context = SharedContext(user, session, (task,), endpoint="android")
    assert context.user_id == user
    assert context.task_ids == (task,)
