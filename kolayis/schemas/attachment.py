import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class AttachmentCreate(BaseModel):
    """Dosya eki yuklerken kullanilacak schema"""
    entity_type: str = Field(
        min_length=1, max_length=50,
        description="Varlik tipi: customer, invoice, quotation"
    )
    entity_id: uuid.UUID = Field(
        description="Bagli oldugu varligin ID'si"
    )
    description: str | None = Field(
        default=None, max_length=255,
        description="Opsiyonel dosya aciklamasi"
    )


class AttachmentResponse(BaseModel):
    """Dosya eki bilgisi dondurmek icin"""
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
