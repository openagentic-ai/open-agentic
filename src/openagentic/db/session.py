"""模块说明（中文）：`src/openagentic/db/session.py`。\n\n该文件负责数据库连接与会话工厂。\n"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from openagentic.config import SETTINGS

engine = create_async_engine(
    SETTINGS.DATABASE_URL,
    echo=SETTINGS.APP_ENV == "development",
    pool_size=20,
    max_overflow=10,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    跨服务 correlation：structlog 已在每条日志中注入 request_id + tenant_id；
    SQL 执行时间可由 engine echo / Postgres log_min_duration_statement + request_id 关联。
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
