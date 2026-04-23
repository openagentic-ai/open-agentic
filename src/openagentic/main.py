"""FastAPI application factory."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openagentic import __version__
from openagentic.config import SETTINGS
from openagentic.db.base import Base
from openagentic.db.session import engine

# Import all models so Alembic can detect them
from openagentic.core.auth.models import User, ApiKey  # noqa: F401
from openagentic.core.chat.models import Conversation, Message  # noqa: F401
from openagentic.agent.models import Agent, AgentExecution  # noqa: F401
from openagentic.workflow.models import Workflow, WorkflowRun  # noqa: F401
from openagentic.knowledge.models import KnowledgeDocument, KnowledgeChunk  # noqa: F401

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Starting OpenAgentic", version=__version__, env=SETTINGS.APP_ENV)

    # Create tables (dev only; production uses Alembic)
    if SETTINGS.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (dev mode)")

    yield

    await engine.dispose()
    logger.info("OpenAgentic shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=SETTINGS.APP_NAME,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check (matches Rust backend's /health)
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": __version__}

    # Register routers
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

    # Backward-compatible endpoints matching Rust backend
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
