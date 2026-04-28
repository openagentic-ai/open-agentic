"""Test Prometheus metrics setup."""

from fastapi import FastAPI

from openagentic.observability.metrics import setup_metrics


class TestMetricsSetup:
    """验证 Prometheus 指标采集的挂载。"""

    def test_setup_metrics_adds_endpoint(self):
        """setup_metrics 应在临时 app 上注册 /metrics 端点。"""
        app = FastAPI()
        setup_metrics(app)

        # 检查路由已注册
        routes = [r.path for r in app.routes]
        assert "/metrics" in routes

    def test_setup_metrics_preserves_existing_routes(self):
        """setup_metrics 不应移除已有的路由。"""
        app = FastAPI()

        @app.get("/custom")
        async def custom():
            return {"ok": True}

        setup_metrics(app)
        routes = [r.path for r in app.routes]
        assert "/custom" in routes
        assert "/metrics" in routes
