import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ServiceOffering(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "service_offerings"
    __table_args__ = (
        CheckConstraint("price_fen >= 0", name="ck_service_price_nonnegative"),
        CheckConstraint("duration_minutes > 0", name="ck_service_duration_positive"),
    )

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_fen: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
