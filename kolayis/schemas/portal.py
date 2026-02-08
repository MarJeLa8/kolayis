"""
Musteri Portali Pydantic semalari.
Giris istekleri ve portal erisim olusturma icin veri dogrulama saglar.
"""

import uuid

from pydantic import BaseModel, Field


class PortalLoginRequest(BaseModel):
    """Portal giris istegi: erisim kodu + PIN."""
    access_token: str = Field(..., min_length=1, description="Musteri erisim kodu")
    pin: str = Field(..., min_length=4, max_length=6, description="4-6 haneli PIN")


class PortalAccessCreate(BaseModel):
    """Yeni portal erisimi olusturma istegi."""
    customer_id: uuid.UUID = Field(..., description="Musteri ID")
    pin: str = Field(
        ...,
        min_length=4,
        max_length=6,
        pattern=r"^\d{4,6}$",
        description="4-6 haneli PIN (sadece rakam)",
    )
