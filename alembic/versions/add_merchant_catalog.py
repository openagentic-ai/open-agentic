"""Add merchants, owner memberships and service catalog.

Revision ID: 51b4d9e20a71
Revises: 3f2c8e7a1b90
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "51b4d9e20a71"
down_revision = "3f2c8e7a1b90"
branch_labels = None
depends_on = None


def _base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "merchants", *_base_columns(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False),
        sa.Column("contact_phone", sa.String(32), nullable=False),
    )
    op.create_table(
        "merchant_members", *_base_columns(),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("merchant_id", "user_id", name="uq_merchant_member"),
    )
    op.create_index("ix_merchant_members_merchant_id", "merchant_members", ["merchant_id"])
    op.create_index("ix_merchant_members_user_id", "merchant_members", ["user_id"])
    op.create_table(
        "service_offerings", *_base_columns(),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_fen", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("availability_note", sa.String(500), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price_fen >= 0", name="ck_service_price_nonnegative"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_service_duration_positive"),
    )
    op.create_index("ix_service_offerings_merchant_id", "service_offerings", ["merchant_id"])


def downgrade() -> None:
    op.drop_table("service_offerings")
    op.drop_table("merchant_members")
    op.drop_table("merchants")
