import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Invoice(Base):
    """
    Fatura modeli.
    Bir musteriye kesilen faturayi temsil eder.
    Fatura kalemleri (InvoiceItem) ile birlikte calısır.
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Fatura bilgileri
    invoice_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    # Fatura tarihi ve vade tarihi
    invoice_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    # Durum: draft (taslak), sent (gonderildi), paid (odendi), cancelled (iptal)
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )
    # Aciklama/not
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Toplam tutarlar (fatura kalemleri hesaplandiktan sonra guncellenir)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    customer: Mapped["Customer"] = relationship()
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    @property
    def paid_amount(self) -> Decimal:
        """Toplam odenen miktar."""
        return sum((p.amount for p in self.payments), Decimal("0.00"))

    @property
    def remaining_amount(self) -> Decimal:
        """Kalan borc miktari."""
        remaining = self.total - self.paid_amount
        return max(remaining, Decimal("0.00"))


class InvoiceItem(Base):
    """
    Fatura kalemi modeli.
    Faturadaki her bir satiri temsil eder.
    Ornek: 5 adet "Mutfak Dolabi" x 3000 TL = 15000 TL
    """

    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Kalem bilgileri (urun silinse bile faturada kalmasi icin ayri tutuyoruz)
    description: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    tax_rate: Mapped[int] = mapped_column(
        Integer, default=20
    )
    # Hesaplanan degerler
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    # Iliski
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()
