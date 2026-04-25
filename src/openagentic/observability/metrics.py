"""模块说明（中文）：`src/openagentic/observability/metrics.py`。

Prometheus `/metrics` 端点。

只用 method/path_template/status 三维标签，不带 tenant 维度——
租户级聚合走日志（已带 tenant_id），metrics 控制基数避免 Prometheus 爆炸。
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app: FastAPI) -> None:
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
