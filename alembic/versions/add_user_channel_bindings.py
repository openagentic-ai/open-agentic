"""add user_channel_bindings table

外部渠道账号（飞书 open_id / 企微 user_id / ...）→ OpenAgentic User 的映射表。
取代 env OPENAGENTIC_BOT_USER_ID 的单租户兜底。

Revision ID: c8e2d109b34f
Revises: b7f1c08e9a23
Create Date: 2026-04-28 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c8e2d109b34f"
down_revision: Union[str, None] = "b7f1c08e9a23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_channel_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "external_id", name="uq_user_channel_bindings_platform_eid"),
    )
    op.create_index(
        "ix_user_channel_bindings_user_id_platform",
        "user_channel_bindings",
        ["user_id", "platform"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_channel_bindings_user_id_platform", table_name="user_channel_bindings")
    op.drop_table("user_channel_bindings")
