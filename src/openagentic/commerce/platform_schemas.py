from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from openagentic.catalog.schemas import ServiceInput


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GrantInput(Input):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[Literal["services:read", "quotes:write", "orders:read"]] = Field(
        min_length=1, max_length=3
    )
    expires_days: int = Field(default=7, ge=1, le=30)


class QuoteInput(Input):
    service_id: UUID


class QuoteConfirmation(Input):
    preferred_at: AwareDatetime
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=1, max_length=32)
    note: str = Field(default="", max_length=2000)
    confirmed: Literal[True]


class QuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    merchant_id: UUID
    service_name: str
    price_fen: int
    duration_minutes: int
    expires_at: datetime
    confirmed_order_id: UUID | None

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class ToolCall(Input):
    arguments: dict = Field(default_factory=dict)


class SearchArguments(Input):
    q: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    limit: int = Field(default=20, ge=1, le=100)


class OrderArguments(Input):
    order_id: UUID


class ImportedOffering(ServiceInput):
    external_id: str = Field(min_length=1, max_length=100)


class CatalogImport(Input):
    system: str = Field(min_length=1, max_length=100)
    services: list[ImportedOffering] = Field(min_length=1, max_length=100)


class PilotLogInput(Input):
    order_id: UUID | None = None
    actor: Literal["founder", "team"]
    category: Literal["onboarding", "operation", "support"]
    minutes: int = Field(ge=0, le=1440)
    attribution: Literal["existing_customer", "new_platform", "unknown"] = "unknown"
    note: str = Field(min_length=1, max_length=1500)


class FeeInput(Input):
    basis_points: int = Field(ge=0, le=10000)
    flat_fen: int = Field(default=0, ge=0, le=1000000)


class PaymentInput(Input):
    request_id: UUID
    confirmed: Literal[True]


class RefundInput(Input):
    reason: str = Field(min_length=1, max_length=2000)


class RefundResolution(Input):
    approve: bool
    resolution: str = Field(min_length=1, max_length=2000)


class CaseInput(Input):
    subject: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=3000)


class CaseResolution(Input):
    resolution: str = Field(min_length=1, max_length=3000)
