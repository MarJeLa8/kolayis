"""
Teklif (Proforma Fatura) modeli.
Musteriye gonderilen teklifleri temsil eder.
Kabul edildikten sonra faturaya cevrilebilir.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Quotation(Base):
    """
    Teklif modeli.
    Bir musteriye verilen teklifi/proforma faturayi temsil eder.
    Teklif kalemleri (QuotationItem) ile birlikte calisir.
    """

    __tablename__ = "quotations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Teklif bilgileri
    quotation_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    # Teklif tarihi ve gecerlilik tarihi
    quotation_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    valid_until: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    # Durum: draft (taslak), sent (gonderildi), accepted (kabul edildi),
    #         rejected (reddedildi), converted (faturaya cevrildi)
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )
    # Aciklama/not
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Toplam tutarlar (teklif kalemleri hesaplandiktan sonra guncellenir)
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
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationItem(Base):
    """
    Teklif kalemi modeli.
    Teklifteki her bir satiri temsil eder.
    Ornek: 5 adet "Web Sitesi Tasarimi" x 5000 TL = 25000 TL
    """

    __tablename__ = "quotation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Kalem bilgileri (urun silinse bile teklifte kalmasi icin ayri tutuyoruz)
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
    quotation: Mapped["Quotation"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()
