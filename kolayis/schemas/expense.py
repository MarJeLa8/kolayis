import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


# --- Kategori Schemalari ---

class ExpenseCategoryCreate(BaseModel):
    """Yeni gelir-gider kategorisi olusturmak icin"""
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6366f1", max_length=7)


class ExpenseCategoryResponse(BaseModel):
    """Kategori bilgisi dondurmek icin"""
    id: uuid.UUID
    name: str
    color: str
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Gelir-Gider Schemalari ---

class ExpenseCreate(BaseModel):
    """Yeni gelir veya gider kaydi olusturmak icin"""
    category_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    expense_date: date
    expense_type: str = Field(pattern="^(income|expense)$")
    payment_method: str | None = None
    notes: str | None = None


class ExpenseUpdate(BaseModel):
    """Gelir/gider kaydini guncellemek icin. Tum alanlar opsiyonel (partial update)."""
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    expense_date: date | None = None
    expense_type: str | None = Field(default=None, pattern="^(income|expense)$")
    payment_method: str | None = None
    notes: str | None = None


class ExpenseResponse(BaseModel):
    """Gelir/gider bilgisi dondurmek icin"""
    id: uuid.UUID
    category_id: uuid.UUID | None
    description: str
    amount: Decimal
    expense_date: date
    expense_type: str
    payment_method: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseListResponse(BaseModel):
    """Gelir/gider listesi icin (sayfalama destekli)"""
    items: list[ExpenseResponse]
    total: int
    page: int
    size: int
