import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class NoteCreate(BaseModel):
    """Yeni gorusme notu olusturmak icin"""
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    note_type: str = "other"  # phone, email, meeting, other


class NoteUpdate(BaseModel):
    """Not guncellemek icin. Tum alanlar opsiyonel."""
    title: str | None = None
    content: str | None = None
    note_type: str | None = None


class NoteResponse(BaseModel):
    """Not bilgisi dondurmek icin"""
    id: uuid.UUID
    customer_id: uuid.UUID
    author_id: uuid.UUID
    title: str
    content: str
    note_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
