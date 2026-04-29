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
# 这些 import 必须在 configure_logging() 之后，因为模型模块会间接触发 logger 实例化。
from openagentic.core.auth.models import User, ApiKey  # noqa: E402, F401
from openagentic.core.chat.models import Conversation, Message  # noqa: E402, F401
from openagentic.agent.models import Agent, AgentExecution  # noqa: E402, F401
from openagentic.workflow.models import Workflow, WorkflowExecution  # noqa: E402, F401
from openagentic.knowledge.models import KnowledgeBase, Document, Chunk  # noqa: E402, F401
from openagentic.channels.models import ChannelConfig  # noqa: E402, F401

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期。

    说明：
    - 开发环境会调用 create_all 兜底建表，便于本地快速跑通；
    - 生产环境应使用 Alembic 迁移，不依赖 create_all；
    - 启动时启动渠道长连接（飞书 WebSocket 等），关闭时释放。
    """
    logger.info("Starting OpenAgentic", version=__version__, env=SETTINGS.APP_ENV)

    # 仅开发环境自动建表：生产请使用 `alembic upgrade head`。
    if SETTINGS.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (dev mode)")

    # 启动渠道长连接（飞书 WebSocket 等）
    from extensions.channels import start_channels
    await start_channels()

    yield

    # 关闭渠道长连接
    from extensions.channels import stop_channels
    await stop_channels()

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
    from openagentic.memory.router import router as memory_router
    from openagentic.skills.router import router as skills_router
    from openagentic.core.chat.sessions_router import router as sessions_router
    from openagentic.channels.router import router as channels_mgmt_router
    from openagentic.devices.router import router as devices_router

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(llm_router)
    app.include_router(agent_router)
    app.include_router(workflow_router)
    app.include_router(knowledge_router)
    app.include_router(memory_router)
    app.include_router(skills_router)
    app.include_router(sessions_router)
    app.include_router(channels_mgmt_router)
    app.include_router(devices_router)

    @app.get("/api/presence")
    async def get_presence():
        return {"status": "online"}

    # ---------- 渠道集成：飞书 + 企业微信 webhook 路由 ----------
    _setup_channel_routes(app)

    return app


def _setup_channel_routes(app: FastAPI) -> None:
    """注册飞书/企业微信渠道 webhook 路由（与 core 完全解耦）。

    渠道由环境变量自动发现——未配置则静默跳过，零开销。
    agent 回调通过 ConversationEngine（共享底座）处理消息。
    """
    from openagentic.agent.engine import ConversationEngine
    from openagentic.identity import DEFAULT_SYSTEM_PROMPT
    from extensions.channels import register_channel_routes, set_agent_callback
    from extensions.channels.base import IncomingMessage

    _channel_engine = ConversationEngine(
        model=SETTINGS.LITELLM_DEFAULT_MODEL,
        api_key=SETTINGS.OPENAI_API_KEY or "",
        tools=[],
        system_prompt=DEFAULT_SYSTEM_PROMPT + (
            "\n当前通过飞书/企业微信渠道接入。"
        ),
    )

    async def _channel_agent_callback(msg: IncomingMessage) -> str:
        # 通过并发底座：同 chat_id 串行 + 全局/LLM 类别限流，与 ChannelAIService 同一套配额。
        from openagentic.concurrency import get_default_gate, GateBusy, GateTimeout

        async def _run() -> str:
            messages = [
                {"role": "system", "content": _channel_engine.system_prompt},
                {"role": "user", "content": msg.text},
            ]
            return await _channel_engine.chat(messages) or "（未返回内容）"

        try:
            return await get_default_gate().submit(
                session_key=msg.chat_id or msg.sender_id,
                coro_factory=_run,
            )
        except GateBusy:
            return "服务繁忙，请稍后重试。"
        except GateTimeout:
            return "处理超时，请稍后重试。"
        except Exception:
            logger.exception("Channel agent execution failed for %s", msg.platform)
            return "抱歉，处理消息时遇到错误，请稍后重试。"

    set_agent_callback(_channel_agent_callback)
    register_channel_routes(app)


app = create_app()
