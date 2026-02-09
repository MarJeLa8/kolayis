"""WhatsApp mesaj kaydi modeli."""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class WhatsAppMessage(Base):
    """Gonderilen WhatsApp mesajlarinin kaydi."""

    __tablename__ = "whatsapp_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    # Mesaj bilgileri
    phone_number: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False  # invoice_send, payment_reminder, custom
    )
    message_body: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    # WhatsApp API'den donen mesaj ID
    wa_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    # Durum: pending, sent, delivered, read, failed
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
