"""add system workflow support: is_system, slug, version; user_id nullable

Revision ID: d9f3e109c50a
Revises: c8e2d109b34f
Create Date: 2026-04-29 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9f3e109c50a"
down_revision: Union[str, None] = "c8e2d109b34f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "workflows",
        sa.Column("slug", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint("uq_workflows_slug", "workflows", ["slug"])
    op.create_index("ix_workflows_slug", "workflows", ["slug"])
    op.add_column(
        "workflows",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column(
        "workflows", "user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_constraint("workflows_user_id_fkey", "workflows", type_="foreignkey")
    op.create_foreign_key(
        "workflows_user_id_fkey", "workflows", "users",
        ["user_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("workflows_user_id_fkey", "workflows", type_="foreignkey")
    op.create_foreign_key(
        "workflows_user_id_fkey", "workflows", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.alter_column(
        "workflows", "user_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("workflows", "version")
    op.drop_index("ix_workflows_slug", table_name="workflows")
    op.drop_constraint("uq_workflows_slug", "workflows", type_="unique")
    op.drop_column("workflows", "slug")
    op.drop_column("workflows", "is_system")
