"""
Tekrarlayan fatura Pydantic semalari.
Form dogrulama ve veri transferi icin kullanilir.
"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class RecurringItemCreate(BaseModel):
    """Tekrarlayan fatura kalemi olusturma semasi."""
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    tax_rate: int = Field(default=20, ge=0, le=100)
    product_id: uuid.UUID | None = None


class RecurringCreate(BaseModel):
    """Tekrarlayan fatura olusturma semasi."""
    customer_id: uuid.UUID
    frequency: str = Field(pattern=r"^(weekly|monthly|quarterly|yearly)$")
    start_date: date
    end_date: date | None = None
    notes: str | None = None
    items: list[RecurringItemCreate] = []


class RecurringUpdate(BaseModel):
    """Tekrarlayan fatura guncelleme semasi."""
    frequency: str | None = None
    end_date: date | None = None
    is_active: bool | None = None
    notes: str | None = None
