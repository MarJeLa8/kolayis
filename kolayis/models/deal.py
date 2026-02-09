"""
Satis firsati (Deal) modeli.
Satis pipeline'indaki firsatlari temsil eder.
Lead -> Teklif -> Muzakere -> Kazanildi/Kaybedildi asamalarini takip eder.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class DealStage(Base):
    """
    Pipeline asamasi modeli.
    Kullanici kendi asamalarini tanimlayabilir.
    Varsayilan: Lead, Teklif, Muzakere, Kazanildi, Kaybedildi
    """

    __tablename__ = "deal_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    color: Mapped[str] = mapped_column(
        String(20), default="#6366f1"
    )
    # Sira numarasi (surukle-birak icin)
    position: Mapped[int] = mapped_column(
        Integer, default=0
    )
    # Bu asama kapanmis mi? (kazanildi/kaybedildi gibi son asamalar)
    is_closed: Mapped[bool] = mapped_column(
        default=False
    )
    # Kazanildi mi kaybedildi mi? (sadece is_closed=True ise anlamli)
    is_won: Mapped[bool] = mapped_column(
        default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    deals: Mapped[list["Deal"]] = relationship(back_populates="stage")


class Deal(Base):
    """
    Satis firsati modeli.
    Bir musteri ile iliskili potansiyel satis anlasmasi.
    Pipeline'da suruklenerek asamalar arasi tasinir.
    """

    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Hangi musteriye ait
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Hangi asamada
    stage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deal_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Iliskili teklif (opsiyonel)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True
    )

    # Firsat bilgileri
    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # Beklenen tutar
    value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )
    # Para birimi
    currency: Mapped[str] = mapped_column(
        String(10), default="TRY"
    )
    # Kazanma olasiligi (%)
    probability: Mapped[int] = mapped_column(
        Integer, default=50
    )
    # Beklenen kapanma tarihi
    expected_close_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    # Notlar
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Oncelik: low, medium, high
    priority: Mapped[str] = mapped_column(
        String(20), default="medium"
    )
    # Pipeline'daki sira (ayni asamadaki deal'lar arasinda siralama)
    position: Mapped[int] = mapped_column(
        Integer, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
    stage: Mapped["DealStage"] = relationship(back_populates="deals")
    quotation: Mapped["Quotation | None"] = relationship()
