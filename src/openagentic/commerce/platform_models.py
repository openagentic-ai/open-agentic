"""Open commerce: quotes, delegated Agent access, pilot evidence and finance."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from openagentic.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_agent_grants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class PriceQuote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_quotes"

    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_offerings.id")
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"))
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce_agent_grants.id")
    )
    service_name: Mapped[str] = mapped_column(String(100))
    price_fen: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_orders.id")
    )


class ToolAudit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_tool_audits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce_agent_grants.id")
    )
    tool_name: Mapped[str] = mapped_column(String(100))
    arguments_digest: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)


class ImportedService(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_imported_services"
    __table_args__ = (
        UniqueConstraint("merchant_id", "system", "external_id", name="uq_imported_service"),
    )

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_offerings.id")
    )
    system: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str] = mapped_column(String(100))


class PilotLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_pilot_logs"
    __table_args__ = (CheckConstraint("minutes >= 0", name="ck_pilot_minutes"),)

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_orders.id")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(30))
    minutes: Mapped[int] = mapped_column(Integer)
    attribution: Mapped[str] = mapped_column(String(30), default="unknown")
    note: Mapped[str] = mapped_column(Text)


class FeePolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_fee_policies"
    __table_args__ = (
        CheckConstraint("basis_points >= 0 AND basis_points <= 10000", name="ck_fee_basis_points"),
        CheckConstraint("flat_fen >= 0", name="ck_fee_flat"),
    )

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), unique=True
    )
    basis_points: Mapped[int] = mapped_column(Integer, default=0)
    flat_fen: Mapped[int] = mapped_column(Integer, default=0)


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_payments"
    __table_args__ = (
        CheckConstraint(
            "amount_fen >= 0 AND fee_fen >= 0 AND fee_fen <= amount_fen", name="ck_payment_amounts"
        ),
        CheckConstraint("status IN ('paid', 'refunded')", name="ck_payment_status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_orders.id"), unique=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(30))
    provider_reference: Mapped[str] = mapped_column(String(100), unique=True)
    amount_fen: Mapped[int] = mapped_column(Integer)
    fee_fen: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))


class Refund(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_refunds"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_refund_payment"),
        CheckConstraint(
            "status IN ('requested', 'processed', 'declined')", name="ck_refund_status"
        ),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commerce_payments.id")
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="requested")
    resolution: Mapped[str] = mapped_column(Text, default="")


class SupportCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_support_cases"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking_orders.id"), index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")


class IntegrationDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "commerce_integration_deliveries"
    __table_args__ = (
        UniqueConstraint("order_id", "system", name="uq_integration_delivery"),
        CheckConstraint("attempts >= 0", name="ck_delivery_attempts"),
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("booking_orders.id"))
    system: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(200), default="")
    acknowledgment: Mapped[dict] = mapped_column(JSON, default=dict)


PLATFORM_MODELS = (
    AgentGrant,
    PriceQuote,
    ToolAudit,
    ImportedService,
    PilotLog,
    FeePolicy,
    Payment,
    Refund,
    SupportCase,
    IntegrationDelivery,
)
