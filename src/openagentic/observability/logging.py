"""模块说明（中文）：`src/openagentic/observability/logging.py`。

structlog 配置：每条日志自动带 `request_id` 与 `tenant_id`（如有）。
开发环境彩色控制台、生产环境 JSON。同时将日志落盘到项目 `log/` 目录。
"""

import logging
from pathlib import Path

import structlog

from openagentic.tenant import get_current_request_id, get_current_tenant_id

# 项目根目录（open-agentic/）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"


def _inject_request_context(logger, method_name, event_dict):
    """structlog processor：把 request_id/tenant_id 塞进每条日志。"""
    rid = get_current_request_id()
    tid = get_current_tenant_id()
    if rid and "request_id" not in event_dict:
        event_dict["request_id"] = rid
    if tid and "tenant_id" not in event_dict:
        event_dict["tenant_id"] = tid
    return event_dict


class _FileWriter:
    """将 structlog 输出同时写到文件（不影响控制台输出）。"""

    def __init__(self, file_path: str):
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._f = open(file_path, "a", encoding="utf-8")

    def __call__(self, _logger, method_name, event_dict):
        from structlog.processors import JSONRenderer
        try:
            line = JSONRenderer()(_logger, method_name, event_dict)
            self._f.write(line + "\n")
            self._f.flush()
        except Exception:
            pass
        return event_dict  # 透传，不阻断后续 processor


def configure_logging(*, json_logs: bool = False, level: str = "INFO",
                      log_file: str = "openagentic.log") -> None:
    """初始化 structlog 与标准库 logging 桥接。

    json_logs=True 适合生产（Loki/ELK 解析），False 适合开发可读。
    日志同时输出到控制台（stdout）和 log/<log_file>。
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

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_path = str(_LOG_DIR / log_file)

    structlog.configure(
        processors=[*shared_processors, _FileWriter(file_path), renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 把 stdlib logging 也降到目标级别，避免第三方库刷屏。
    logging.basicConfig(level=log_level, format="%(message)s")
