"""Ozel alan (Custom Field) modelleri."""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class CustomFieldDefinition(Base):
    """Kullanicinin tanimladigi ozel alan sablonu."""

    __tablename__ = "custom_field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Hangi varlik tipine ait: customer, invoice, product, deal
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Alan adi (kullanicinin verdigi)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Alan tipi: text, number, date, select, checkbox, textarea
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Select tipi icin secenekler (JSON dizisi)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Zorunlu mu?
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    # Sira numarasi (gosterim sirasi)
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Aktif mi?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship()


class CustomFieldValue(Base):
    """Bir varliga ait ozel alan degeri."""

    __tablename__ = "custom_field_values"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Hangi varligin ID'si (customer, invoice, vs.)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    # Deger (hepsi text olarak saklanir, tip donusumu frontend/servis tarafinda)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    field: Mapped["CustomFieldDefinition"] = relationship()
