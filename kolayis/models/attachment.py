import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Attachment(Base):
    """
    Dosya eki modeli.
    Musteri, fatura, teklif gibi varliklara dosya eklenmesini saglar.
    Polimorfik iliski: entity_type + entity_id ile herhangi bir varliga baglanabilir.
    """

    __tablename__ = "attachments"

    # Composite index: entity_type + entity_id uzerinden hizli sorgulama
    __table_args__ = (
        Index("ix_attachments_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    # Dosyayi yukleyen kullanici
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Polimorfik iliski: hangi varlik tipine ait? (customer, invoice, quotation)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    # Polimorfik iliski: hangi varligin ID'si?
    entity_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False
    )

    # Diskte saklanan dosya adi (UUID + uzanti, guvenlik icin)
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Kullanicinin yukledigini orijinal dosya adi
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Dosya boyutu (byte cinsinden)
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # MIME tipi (ornegin: application/pdf, image/png)
    mime_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    # Opsiyonel aciklama
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliski
    owner: Mapped["User"] = relationship()
