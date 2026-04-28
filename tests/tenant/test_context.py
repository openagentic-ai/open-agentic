"""Test tenant contextvar operations."""


from openagentic.tenant import (
    get_current_tenant_id,
    set_current_tenant_id,
    get_current_request_id,
    set_current_request_id,
)


class TestTenantContext:
    """验证 contextvar 的基本读写和隔离行为。"""

    def test_defaults_are_none(self):
        """初始状态（先清理再检查），所有 contextvar 应为 None。"""
        # 清理可能被其他测试污染的 contextvar
        set_current_tenant_id(None)
        set_current_request_id(None)
        assert get_current_tenant_id() is None
        assert get_current_request_id() is None

    def test_set_and_get_tenant_id(self):
        """写入后应能正确读出。"""
        set_current_tenant_id("tenant-abc")
        assert get_current_tenant_id() == "tenant-abc"
        # 清理
        set_current_tenant_id(None)

    def test_set_and_get_request_id(self):
        """写入后应能正确读出。"""
        set_current_request_id("req-xyz")
        assert get_current_request_id() == "req-xyz"
        # 清理
        set_current_request_id(None)

    def test_set_tenant_to_none(self):
        """显式设为 None 应清空。"""
        set_current_tenant_id("something")
        set_current_tenant_id(None)
        assert get_current_tenant_id() is None

    def test_set_request_to_none(self):
        set_current_request_id("something")
        set_current_request_id(None)
        assert get_current_request_id() is None

    def test_independent_contextvars(self):
        """tenant_id 和 request_id 的 contextvar 相互独立。"""
        set_current_tenant_id("t1")
        set_current_request_id("r1")
        assert get_current_tenant_id() == "t1"
        assert get_current_request_id() == "r1"

        set_current_tenant_id(None)
        assert get_current_tenant_id() is None
        assert get_current_request_id() == "r1"

        set_current_request_id(None)
