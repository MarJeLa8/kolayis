import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    unit_price: Decimal = Field(ge=0)
    unit: str = "adet"
    tax_rate: int = Field(default=20, ge=0, le=100)
    stock: int | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    unit_price: Decimal | None = None
    unit: str | None = None
    tax_rate: int | None = None
    stock: int | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    unit_price: Decimal
    unit: str
    tax_rate: int
    stock: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
