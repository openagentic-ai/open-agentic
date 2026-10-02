from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MerchantInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=3000)
    contact_name: str = Field(min_length=1, max_length=100)
    contact_phone: str = Field(min_length=1, max_length=32)


class MerchantPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    region: str
    description: str


class MerchantResponse(MerchantPublic):
    contact_name: str
    contact_phone: str
    created_at: datetime
    updated_at: datetime
