import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Notification(Base):
    """
    Bildirim modeli.
    Kullanicilara gonderilen uygulama ici bildirimleri saklar.
    Ornek: fatura odendi, stok azaldi, vade yaklasıyor vb.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    # Bildirimin sahibi (alicisi)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Bildirim tipi: invoice_paid, invoice_overdue, stock_low, customer_new,
    # payment_received, quotation_accepted, recurring_generated, system
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # Bildirim baslik: "Fatura odendi!"
    title: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    # Bildirim mesaji: "FTR-0042 numarali fatura odendi. Tutar: 5.000 TL"
    message: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    # Ilgili varlik (opsiyonel - tiklaninca yonlendirilecek)
    entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )
    # Bildirime tiklaninca gidilecek URL (opsiyonel)
    link: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    # Okundu/okunmadi durumu
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Iliski
    owner: Mapped["User"] = relationship()
