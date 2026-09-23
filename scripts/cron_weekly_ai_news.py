#!/usr/bin/env python3
"""每周五17:00自动触发全球科技/AI新闻周报工作流。

crontab 示例:
    0 17 * * 5 cd /opt/open-agentic && .venv/bin/python scripts/cron_weekly_ai_news.py

工作流按 slug 查找系统预设 ``news.tech_weekly``（应用启动时自动同步预设，
fork 出的用户副本 slug 为 NULL，不会被误触发）。
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://openagentic:openagentic@localhost:5433/openagentic",
)

from sqlalchemy import select

from openagentic.db.session import async_session
from openagentic.workflow.models import Workflow
from openagentic.workflow.service import create_run

WORKFLOW_SLUG = "news.tech_weekly"


async def main() -> None:
    async with async_session() as db:
        workflow = (
            await db.execute(
                select(Workflow)
                .where(Workflow.slug == WORKFLOW_SLUG)
                .order_by(Workflow.created_at.desc())
            )
        ).scalars().first()
        if not workflow:
            print(f"ERROR: 未找到 slug={WORKFLOW_SLUG} 的工作流（系统预设由应用启动时同步）")
            sys.exit(1)
        run = await create_run(db, workflow, input_data={})
        await db.commit()
        print(f"已创建工作流运行: {run.id} (workflow={workflow.name})")


if __name__ == "__main__":
    asyncio.run(main())
