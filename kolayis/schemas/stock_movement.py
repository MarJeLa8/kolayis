import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class StockMovementCreate(BaseModel):
    """
    Stok hareketi olusturma schemasi.
    quantity her zaman pozitif olmali; yonu movement_type belirler.
    """
    product_id: uuid.UUID
    movement_type: str = Field(
        ..., pattern="^(in|out|adjustment)$",
        description="Hareket tipi: in (giris), out (cikis), adjustment (duzeltme)"
    )
    quantity: int = Field(gt=0, description="Miktar (pozitif tam sayi)")
    notes: str | None = None


class StockMovementResponse(BaseModel):
    """Stok hareketi yanit schemasi."""
    id: uuid.UUID
    product_id: uuid.UUID
    movement_type: str
    quantity: int
    reference_type: str | None
    reference_id: uuid.UUID | None
    notes: str | None
    previous_stock: int
    new_stock: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
