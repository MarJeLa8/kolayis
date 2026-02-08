import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Payment(Base):
    """
    Odeme modeli.
    Bir faturaya yapilan kismi veya tam odemeyi temsil eder.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(50), default="bank_transfer"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliski
    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
