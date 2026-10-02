from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class BookingInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    service_id: UUID
    request_id: UUID
    expected_price_fen: int = Field(ge=0, le=100_000_000, strict=True)
    preferred_at: AwareDatetime
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=1, max_length=32)
    note: str = Field(default="", max_length=2000)
    confirmed: Literal[True]


class BookingStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "completed", "declined"]


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    service_id: UUID
    service_name: str
    price_fen: int
    duration_minutes: int
    preferred_at: datetime
    customer_name: str
    customer_phone: str
    note: str
    status: Literal["pending", "accepted", "completed", "declined", "cancelled"]
    created_at: datetime
    updated_at: datetime

    @field_validator("preferred_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
