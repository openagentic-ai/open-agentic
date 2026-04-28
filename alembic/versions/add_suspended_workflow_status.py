"""add suspended to workflow execution status enum

Phase 7 Sub-milestone 1.1：节点级挂起需要新增 'suspended' 状态。

注意：项目存在历史枚举命名分歧——
- add_workflow_tables.py 在生产链上创建了 'workflowrunstatus'（值含 'success'，与现模型不一致）
- 现 SQLAlchemy 模型 ExecutionStatus 在 dev create_all 路径下生成 'executionstatus'
两个枚举名都需要新增 'suspended'，以兼容已有部署的两条路径。

Revision ID: b7f1c08e9a23
Revises: a1b2c3d4e5f6
Create Date: 2026-04-28 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7f1c08e9a23"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL: ALTER TYPE ... ADD VALUE 必须在事务外执行；
    # alembic 默认每个迁移在事务内运行，所以用 COMMIT/BEGIN 包裹。
    # IF NOT EXISTS 保证幂等。
    op.execute("COMMIT")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'executionstatus') THEN
                ALTER TYPE executionstatus ADD VALUE IF NOT EXISTS 'suspended';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflowrunstatus') THEN
                ALTER TYPE workflowrunstatus ADD VALUE IF NOT EXISTS 'suspended';
            END IF;
        END$$;
        """
    )
    op.execute("BEGIN")


def downgrade() -> None:
    # PostgreSQL 不支持从 enum 直接移除值（仅能重建枚举类型，代价高且需停机）。
    # 'suspended' 状态在 downgrade 后只是不再被业务代码写入，存量记录中保留亦无害。
    pass
