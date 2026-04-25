"""模块说明（中文）：`src/openagentic/observability/middleware.py`。

请求上下文 ASGI 中间件：
- 生成或透传 `X-Request-ID`，写入 contextvar 并回写响应头
- 解析 Authorization Bearer JWT 提取 `sub` 写入 tenant contextvar（不强制鉴权）

为何不用 Starlette `BaseHTTPMiddleware`？该实现会在独立 task 内 await 下游，
contextvars 在某些边界（流式响应、background task）传播不稳定；
裸 ASGI middleware 在同一 task 内设值，覆盖最稳。
"""

import uuid

from openagentic.core.auth.service import decode_token
from openagentic.tenant import set_current_request_id, set_current_tenant_id


class RequestContextMiddleware:
    """注入 request_id / tenant_id 到 contextvars，供日志和 metrics 用。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        set_current_request_id(request_id)

        tenant_id: str | None = None
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            payload = decode_token(token)
            if payload:
                sub = payload.get("sub")
                if sub:
                    tenant_id = str(sub)
        set_current_tenant_id(tenant_id)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = hdrs
            await send(message)

        await self.app(scope, receive, send_wrapper)
