"""Run the merchant workspace locally, with SQLite and no model/network calls.

Build ui/dist first, then run:
    PYTHONPATH=src .venv/bin/python scripts/run_merchant_demo.py

This demo persists real data separately from the production PostgreSQL database.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from openagentic.catalog.models import ServiceOffering
from openagentic.apps.commerce import mount_commerce
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import PLATFORM_MODELS
from openagentic.commerce.payments import LocalPaymentProvider
from openagentic.core.auth.models import ApiKey, User
from openagentic.core.auth.router import router as auth_router
from openagentic.core.chat.models import Conversation, Message
from openagentic.db.base import Base
from openagentic.db.session import get_db
from openagentic.merchants.models import Merchant, MerchantMember
from openagentic.memory.router import router as memory_router

ROOT = Path(__file__).resolve().parents[1]


class SPAFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code == 404
                and not path.startswith("api/")
                and "." not in Path(path).name
            ):
                return await super().get_response("index.html", scope)
            raise


def create_demo_app(data_dir: Path | None = None) -> FastAPI:
    directory = data_dir or ROOT / "data" / "merchant-demo"
    directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("OPENAGENTIC_MEMORY_DIR", str(directory / "memory"))
    database = directory / "merchant.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    @asynccontextmanager
    async def lifespan(_app):
        async with engine.begin() as conn:
            tables = [
                User.__table__,
                ApiKey.__table__,
                Conversation.__table__,
                Message.__table__,
                Merchant.__table__,
                MerchantMember.__table__,
                ServiceOffering.__table__,
                BookingOrder.__table__,
                *(model.__table__ for model in PLATFORM_MODELS),
            ]
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
        yield
        await engine.dispose()

    async def demo_database():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app = FastAPI(title="OpenAgentic Local Merchant Demo", lifespan=lifespan)
    app.state.payment_provider = LocalPaymentProvider()
    app.include_router(auth_router)
    app.include_router(memory_router)
    mount_commerce(app)
    app.dependency_overrides[get_db] = demo_database
    app.mount("/", SPAFiles(directory=str(ROOT / "ui" / "dist"), html=True), name="workspace")
    return app


if __name__ == "__main__":
    if not (ROOT / "ui" / "dist" / "index.html").exists():
        raise SystemExit("请先在 ui/ 运行 npm run build，然后再启动本地工作台。")
    uvicorn.run(create_demo_app(), host="127.0.0.1", port=8766)
