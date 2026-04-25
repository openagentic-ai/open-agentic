"""模块说明（中文）：`src/openagentic/observability/logging.py`。

structlog 配置：每条日志自动带 `request_id` 与 `tenant_id`（如有）。
开发环境彩色控制台、生产环境 JSON。
"""

import logging

import structlog

from openagentic.tenant import get_current_request_id, get_current_tenant_id


def _inject_request_context(logger, method_name, event_dict):
    """structlog processor：把 request_id/tenant_id 塞进每条日志。"""
    rid = get_current_request_id()
    tid = get_current_tenant_id()
    if rid and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    if tid and "tenant_id" not in event_dict:
        event_dict["tenant_id"] = tid
    return event_dict


def configure_logging(*, json_logs: bool = False, level: str = "INFO") -> None:
    """初始化 structlog 与标准库 logging 桥接。

    json_logs=True 适合生产（Loki/ELK 解析），False 适合开发可读。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_request_context,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 把 stdlib logging 也降到目标级别，避免第三方库刷屏。
    logging.basicConfig(level=log_level, format="%(message)s")
