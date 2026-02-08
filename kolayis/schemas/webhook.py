import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class WebhookCreate(BaseModel):
    """Yeni webhook olusturma schemasi."""
    url: str = Field(min_length=1, max_length=500)
    secret: str = Field(min_length=1, max_length=255)
    events: list[str] = Field(min_length=1)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class WebhookUpdate(BaseModel):
    """Webhook guncelleme schemasi. Tum alanlar opsiyonel."""
    url: str | None = Field(default=None, max_length=500)
    secret: str | None = Field(default=None, max_length=255)
    events: list[str] | None = None
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    """Webhook API yanit schemasi."""
    id: uuid.UUID
    url: str
    events: str
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookLogResponse(BaseModel):
    """Webhook log API yanit schemasi."""
    id: uuid.UUID
    webhook_id: uuid.UUID
    event: str
    payload: str
    response_status: int | None
    response_body: str | None
    success: bool
    sent_at: datetime
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)
