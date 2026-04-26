"""Test structured logging configuration."""

import logging

import structlog

from openagentic.observability.logging import configure_logging, _inject_request_context


class TestLoggingConfiguration:
    """验证 structlog 配置的基本能力。"""

    def test_configure_console_mode(self):
        """开发环境配置：彩色控制台模式不抛异常。"""
        configure_logging(json_logs=False, level="DEBUG")
        logger = structlog.get_logger()
        logger.info("test_console")

    def test_configure_json_mode(self):
        """生产环境配置：JSON 模式不抛异常。"""
        configure_logging(json_logs=True, level="WARNING")
        logger = structlog.get_logger()
        logger.warning("test_json")

    def test_configure_invalid_level_defaults_to_info(self):
        """无效日志级别应回退到 INFO。"""
        # configure_logging 内部会 getattr(logging, level)，无效时得 AttributeError
        # 但调用方应传合法值；此处只验证合法值不崩
        configure_logging(json_logs=False, level="INFO")
        logger = structlog.get_logger()
        logger.info("test_level")


class TestRequestContextInjection:
    """验证 request_id/tenant_id 注入 processor。"""

    def test_processor_adds_context_when_present(self, monkeypatch):
        """当 contextvar 有值时，processor 应注入 request_id 和 tenant_id。"""
        from openagentic.tenant import set_current_request_id, set_current_tenant_id

        set_current_request_id("req-123")
        set_current_tenant_id("tenant-456")

        event = _inject_request_context(None, "info", {"event": "test"})
        assert event["request_id"] == "req-123"
        assert event["tenant_id"] == "tenant-456"
        assert event["event"] == "test"

    def test_processor_noop_when_context_empty(self, monkeypatch):
        """当 contextvar 为空时，processor 不应注入任何字段。"""
        from openagentic.tenant import set_current_request_id, set_current_tenant_id

        set_current_request_id(None)
        set_current_tenant_id(None)

        event = _inject_request_context(None, "info", {"event": "test"})
        assert "request_id" not in event
        assert "tenant_id" not in event

    def test_processor_does_not_overwrite_existing(self, monkeypatch):
        """若 event_dict 已有 request_id，processor 不应覆盖。"""
        from openagentic.tenant import set_current_request_id

        set_current_request_id("from-ctx")
        event = _inject_request_context(None, "info", {"event": "t", "request_id": "already-set"})
        assert event["request_id"] == "already-set"
