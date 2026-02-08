import uuid
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class InvoiceItemCreate(BaseModel):
    product_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    tax_rate: int = Field(default=20, ge=0, le=100)


class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: int
    line_total: Decimal
    tax_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_date: date
    due_date: date | None = None
    status: str = "draft"
    notes: str | None = None
    items: list[InvoiceItemCreate] = []


class InvoiceUpdate(BaseModel):
    customer_id: uuid.UUID
    invoice_date: date
    due_date: date | None = None
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    status: str
    notes: str | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[InvoiceItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
