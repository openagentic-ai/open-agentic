"""Add confirmed booking requests and fulfillment states.

Revision ID: 7c40e13a92bf
Revises: 51b4d9e20a71
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7c40e13a92bf"
down_revision = "51b4d9e20a71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "booking_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("service_offerings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("price_fen", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("preferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_name", sa.String(100), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("buyer_id", "request_id", name="uq_booking_buyer_request"),
        sa.CheckConstraint("price_fen >= 0", name="ck_booking_price_nonnegative"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'completed', 'declined', 'cancelled')",
                           name="ck_booking_status"),
    )
    op.create_index("ix_booking_orders_buyer_id", "booking_orders", ["buyer_id"])
    op.create_index("ix_booking_orders_merchant_id", "booking_orders", ["merchant_id"])


def downgrade() -> None:
    op.drop_table("booking_orders")
