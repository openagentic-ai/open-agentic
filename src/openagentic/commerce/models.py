import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BookingOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "booking_orders"
    __table_args__ = (
        UniqueConstraint("buyer_id", "request_id", name="uq_booking_buyer_request"),
        CheckConstraint("price_fen >= 0", name="ck_booking_price_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'completed', 'declined', 'cancelled')",
            name="ck_booking_status",
        ),
    )

    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_offerings.id", ondelete="RESTRICT"),
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_fen: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
