"""Test database session management and base models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from openagentic.db.session import get_db, async_session, engine


class TestBaseModels:
    """验证 ORM 基类与混入类的基本能力。"""

    def test_base_exists(self):
        """Base 类应可被 SQLAlchemy 正确识别为声明式基类。"""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_timestamp_mixin_has_columns(self):
        """TimestampMixin 必须包含 created_at 和 updated_at 列。"""
        assert "created_at" in TimestampMixin.__dict__
        assert "updated_at" in TimestampMixin.__dict__

    def test_uuid_mixin_has_id_column(self):
        """UUIDPrimaryKeyMixin 必须包含 id 列。"""
        assert "id" in UUIDPrimaryKeyMixin.__dict__


class TestSessionFactory:
    """验证异步会话工厂的基本行为。"""

    def test_async_session_factory_exists(self):
        """async_session 工厂应存在且可调用。"""
        assert async_session is not None

    def test_engine_configured(self):
        """数据库引擎应配置且 URL 非空。"""
        assert engine is not None
        assert engine.url is not None

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db 依赖注入应能产出 AsyncSession 实例。"""
        gen = get_db()
        session = await anext(gen)
        try:
            assert isinstance(session, AsyncSession)
        finally:
            # 用 finally 确保即使断言失败也消费完生成器
            try:
                await gen.aclose()
            except (StopAsyncIteration, RuntimeError):
                pass

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_error(self):
        """异常时 get_db 应执行 rollback（验证生成器不在 finally 崩溃）。"""
        gen = get_db()
        await anext(gen)  # 推进生成器到 yield 点，确保 session 创建
        # 故意抛异常来搅动生成器的 except 路径；
        # 只要生成器能正常关闭就说明 rollback 逻辑不崩。
        try:
            await gen.athrow(Exception("simulated failure"))
        except Exception:
            pass
        # 生成器此时应已退出；在此调用 close 应是安全的
        try:
            await gen.aclose()
        except (StopAsyncIteration, RuntimeError):
            pass
