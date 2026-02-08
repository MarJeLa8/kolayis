import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_date: date
    payment_method: str = "bank_transfer"
    notes: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_date: date
    payment_method: str
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
