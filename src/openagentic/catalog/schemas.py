from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from openagentic.merchants.schemas import MerchantPublic


class ServiceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=3000)
    price_fen: int = Field(ge=0, le=100_000_000, strict=True)
    duration_minutes: int = Field(ge=1, le=10080, strict=True)
    availability_note: str = Field(default="", max_length=500)
    is_published: bool = False


class ServicePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant_id: UUID
    name: str
    description: str
    price_fen: int
    duration_minutes: int
    availability_note: str


class ServiceResponse(ServicePublic):
    is_published: bool
    created_at: datetime
    updated_at: datetime


class StorefrontResponse(BaseModel):
    merchant: MerchantPublic
    services: list[ServicePublic]
