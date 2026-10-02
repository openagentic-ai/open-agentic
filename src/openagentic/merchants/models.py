"""商家资料与成员关系；公开店铺资料不包含经营联系人。"""

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Merchant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "merchants"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)


class MerchantMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "merchant_members"
    __table_args__ = (UniqueConstraint("merchant_id", "user_id", name="uq_merchant_member"),)

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
