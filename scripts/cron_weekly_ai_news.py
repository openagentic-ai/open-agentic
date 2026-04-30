#!/usr/bin/env python3
"""每周五17:00自动触发全球科技/AI新闻周报工作流"""
import asyncio, sys, os, json

sys.path.insert(0, '/opt/open-agentic/src')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from openagentic.workflow.service import execute_run_by_id
from openagentic.workflow.models import Workflow, WorkflowExecution

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql+asyncpg://openagentic:openagentic@localhost:5433/openagentic')
WORKFLOW_ID = '94f8defe-0054-4f9a-b2d2-30e252e86359'  # 国内+国际版

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        from sqlalchemy import text
        # 获取 workflow
        result = await conn.execute(text("SELECT id FROM workflows WHERE id = :wid"), {"wid": WORKFLOW_ID})
        row = result.fetchone()
        if not row:
            print(f"ERROR: 工作流 {WORKFLOW_ID} 不存在")
            sys.exit(1)
        # 创建 run
        import uuid
        run_id = str(uuid.uuid4())
        now = __import__('datetime').datetime.now()
        await conn.execute(text("""
            INSERT INTO workflow_executions (id, workflow_id, status, created_at, updated_at, input_data)
            VALUES (:rid, :wid, 'pending', :now, :now, '{}')
        """), {"rid": run_id, "wid": WORKFLOW_ID, "now": now})
        await conn.commit()
        print(f"✅ 已创建工作流运行: {run_id}")
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
