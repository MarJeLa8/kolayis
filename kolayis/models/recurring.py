"""
Tekrarlayan Fatura modeli.
Belirli araliklarda otomatik fatura olusturmayi saglar.
Ornek: Her ay 1'inde musteri X'e aylik hizmet bedeli faturasi kesilmesi.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Numeric, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class RecurringInvoice(Base):
    """
    Tekrarlayan fatura modeli.
    Belirli bir siklikta (haftalik, aylik, 3 aylik, yillik) otomatik fatura uretir.
    """

    __tablename__ = "recurring_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Tekrarlama sikligi: weekly, monthly, quarterly, yearly
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    # Baslangic tarihi (ilk faturanin olusturulacagi tarih)
    start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    # Bitis tarihi (opsiyonel - None ise surekli devam eder)
    end_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    # Bir sonraki fatura olusturma tarihi
    next_run_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    # Aktif/pasif durumu
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    # Not/aciklama
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Son fatura olusturma zamani
    last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Toplam olusturulan fatura sayisi
    total_generated: Mapped[int] = mapped_column(
        Integer, default=0
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
    items: Mapped[list["RecurringInvoiceItem"]] = relationship(
        back_populates="recurring_invoice", cascade="all, delete-orphan"
    )

    @property
    def frequency_label(self) -> str:
        """Siklik etiketini Turkce dondur."""
        labels = {
            "weekly": "Haftalik",
            "monthly": "Aylik",
            "quarterly": "3 Aylik",
            "yearly": "Yillik",
        }
        return labels.get(self.frequency, self.frequency)


class RecurringInvoiceItem(Base):
    """
    Tekrarlayan fatura kalemi.
    Her tekrarlayan fatura icin sabit kalemler (urun/hizmet satirlari).
    Fatura olusturulurken bu kalemler kopyalanir.
    """

    __tablename__ = "recurring_invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    recurring_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Kalem bilgileri
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

    # Iliski
    recurring_invoice: Mapped["RecurringInvoice"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()
