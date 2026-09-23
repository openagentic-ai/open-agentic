from uuid import uuid4

from openagentic.application.endpoint_gateway import EndpointGateway


def test_web_android_feishu_use_same_context_shape():
    user, session, task = uuid4(), uuid4(), uuid4()
    contexts = [EndpointGateway(endpoint).context(user, session, [task]) for endpoint in ("web", "android", "feishu")]
    assert {(context.user_id, context.session_id, context.task_ids) for context in contexts} == {(user, session, (task,))}
