import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CustomerCreate(BaseModel):
    """Yeni musteri olusturmak icin"""
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    tax_number: str | None = None
    status: str = "active"


class CustomerUpdate(BaseModel):
    """Musteri guncellemek icin. Tum alanlar opsiyonel (partial update)."""
    company_name: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    tax_number: str | None = None
    status: str | None = None


class CustomerResponse(BaseModel):
    """Musteri bilgisi dondurmek icin"""
    id: uuid.UUID
    company_name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    address: str | None
    tax_number: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    """Musteri listesi icin (sayfalama destekli)"""
    items: list[CustomerResponse]
    total: int
    page: int
    size: int
