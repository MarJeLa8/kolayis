import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Webhook(Base):
    """
    Webhook modeli.
    Kullanicinin dis sistemlere bildirim gondermek icin tanimladigi
    webhook endpoint'lerini temsil eder.

    Desteklenen olaylar (events alani JSON string olarak saklanir):
      - invoice.created, invoice.paid, invoice.cancelled
      - customer.created, customer.updated, customer.deleted
      - payment.received
      - product.created, product.updated
    """

    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    # Webhook'u tanimlayan kullanici
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Webhook URL'si: POST istegi gonderilecek adres
    url: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    # HMAC-SHA256 imzalama icin gizli anahtar
    secret: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # Dinlenen olaylar: JSON string formatinda liste
    # Ornek: '["invoice.created", "payment.received"]'
    events: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    # Webhook aktif mi? Pasif yapilirsa istek gonderilmez
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    # Kullanicinin webhook icin yazdigi aciklama
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    logs: Mapped[list["WebhookLog"]] = relationship(
        back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookLog(Base):
    """
    Webhook log modeli.
    Her webhook tetiklenmesinin sonucunu kaydeder.
    Basarili veya basarisiz tum gonderimler loglanir.
    """

    __tablename__ = "webhook_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Tetiklenen olay: ornegin "invoice.created"
    event: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # Gonderilen JSON payload
    payload: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    # Hedef sunucudan donen HTTP status kodu (basarisiz baglantida None)
    response_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Hedef sunucudan donen yanit govdesi
    response_body: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Gonderim basarili mi? (status 2xx ise True)
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    # Gonderim zamani
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Hata mesaji (baglanti hatasi, timeout vb.)
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Iliski
    webhook: Mapped["Webhook"] = relationship(back_populates="logs")
