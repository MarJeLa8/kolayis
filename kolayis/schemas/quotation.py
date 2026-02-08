"""
Teklif (Quotation) Pydantic semalari.
Validasyon ve API response icin kullanilir.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class QuotationItemCreate(BaseModel):
    """Teklif kalemi olusturma semasi."""
    product_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    tax_rate: int = Field(default=20, ge=0, le=100)


class QuotationItemResponse(BaseModel):
    """Teklif kalemi response semasi."""
    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: int
    line_total: Decimal
    tax_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class QuotationCreate(BaseModel):
    """Teklif olusturma semasi."""
    customer_id: uuid.UUID
    quotation_date: date
    valid_until: date | None = None
    notes: str | None = None
    items: list[QuotationItemCreate] = []


class QuotationUpdate(BaseModel):
    """Teklif guncelleme semasi."""
    notes: str | None = None
    valid_until: date | None = None
    status: str | None = None


class QuotationResponse(BaseModel):
    """Teklif response semasi."""
    id: uuid.UUID
    customer_id: uuid.UUID
    quotation_number: str
    quotation_date: date
    valid_until: date | None
    status: str
    notes: str | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[QuotationItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
