"""模块说明（中文）：`src/openagentic/main.py`。\n\n该文件负责 FastAPI 应用创建、生命周期管理与路由装配。\n"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openagentic import __version__
from openagentic.config import SETTINGS
from openagentic.db.base import Base
from openagentic.db.session import engine
from openagentic.observability import (
    RequestContextMiddleware,
    configure_logging,
    setup_metrics,
)

# 进程启动即配置日志（在 logger 实例化之前）
configure_logging(
    json_logs=SETTINGS.APP_ENV != "development",
    level=SETTINGS.APP_LOG_LEVEL,
)

# 导入全部模型，让 Alembic autogenerate 能完整感知 metadata。
from openagentic.core.auth.models import User, ApiKey  # noqa: F401
from openagentic.core.chat.models import Conversation, Message  # noqa: F401
from openagentic.agent.models import Agent, AgentExecution  # noqa: F401
from openagentic.workflow.models import Workflow, WorkflowExecution  # noqa: F401
from openagentic.knowledge.models import KnowledgeBase, Document, Chunk  # noqa: F401

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期。

    说明：
    - 开发环境会调用 create_all 兜底建表，便于本地快速跑通；
    - 生产环境应使用 Alembic 迁移，不依赖 create_all；
    - 关闭时显式释放数据库引擎，避免连接残留。
    """
    logger.info("Starting OpenAgentic", version=__version__, env=SETTINGS.APP_ENV)

    # 仅开发环境自动建表：生产请使用 `alembic upgrade head`。
    if SETTINGS.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (dev mode)")

    yield

    await engine.dispose()
    logger.info("OpenAgentic shutdown complete")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    app = FastAPI(
        title=SETTINGS.APP_NAME,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 注意中间件顺序：add_middleware 是 LIFO，后加的在外层。
    # 期望调用栈：CORS(外) → RequestContext(内) → app，
    # 所以先 add RequestContext，再 add CORS。
    app.add_middleware(RequestContextMiddleware)

    # CORS 当前配置为全放开，便于开发联调。
    # 生产环境建议按域名白名单收敛。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus /metrics 端点（必须在路由注册前 instrument）
    setup_metrics(app)

    # 健康检查接口：用于容器编排探活与外部监控。
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": __version__}

    # 注册核心业务路由。
    from openagentic.core.auth.router import router as auth_router
    from openagentic.core.chat.router import router as chat_router
    from openagentic.core.llm.router import router as llm_router
    from openagentic.agent.router import router as agent_router
    from openagentic.workflow.router import router as workflow_router
    from openagentic.knowledge.router import router as knowledge_router

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(llm_router)
    app.include_router(agent_router)
    app.include_router(workflow_router)
    app.include_router(knowledge_router)

    # 向后兼容的历史接口占位（旧前端依赖），后续可逐步替换为真实实现。
    @app.get("/api/sessions")
    async def list_sessions_compat():
        """Stub for frontend compatibility — will be replaced in Phase 2."""
        return []

    @app.get("/api/channels")
    async def list_channels_compat():
        """Stub for frontend compatibility."""
        return []

    @app.get("/api/presence")
    async def get_presence():
        return {"status": "online"}

    return app


app = create_app()
