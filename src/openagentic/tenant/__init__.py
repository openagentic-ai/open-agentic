"""模块说明（中文）：`src/openagentic/tenant/__init__.py`。

请求级 tenant context（基于 contextvars）。

约定：本平台 `tenant_id` 等同于 `user_id`；行级隔离已在 db schema 落地，
本模块只负责让"当前请求是哪个租户"在调用栈任意位置可读，
供日志、metrics、跨 service 关联使用。鉴权仍由路由层 Depends 处理。
"""

from contextvars import ContextVar

_tenant_id_ctx: ContextVar[str | None] = ContextVar("openagentic_tenant_id", default=None)
_request_id_ctx: ContextVar[str | None] = ContextVar("openagentic_request_id", default=None)


def get_current_tenant_id() -> str | None:
    return _tenant_id_ctx.get()


def set_current_tenant_id(tenant_id: str | None) -> None:
    _tenant_id_ctx.set(tenant_id)


def get_current_request_id() -> str | None:
    return _request_id_ctx.get()


def set_current_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


__all__ = [
    "get_current_tenant_id",
    "set_current_tenant_id",
    "get_current_request_id",
    "set_current_request_id",
]
