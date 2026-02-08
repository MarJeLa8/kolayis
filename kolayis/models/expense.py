import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class ExpenseCategory(Base):
    """
    Gelir-Gider kategorisi modeli.
    Kullanici kendi kategorilerini tanimlayabilir (ornek: Kira, Maas, Reklam).
    is_default=True olan kategoriler sistem tarafindan olusturulmustur.
    """

    __tablename__ = "expense_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Kategori adi (ornek: "Kira", "Maas", "Satis Geliri")
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    # Kategori rengi (hex kodu, UI'da badge/chip gosterimi icin)
    color: Mapped[str] = mapped_column(
        String(7), default="#6366f1"
    )
    # Sistem tarafindan olusturulan varsayilan kategoriler
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="category"
    )


class Expense(Base):
    """
    Gelir-Gider kaydi modeli.
    expense_type alani "income" (gelir) veya "expense" (gider) olabilir.
    Boylece tek bir tabloda hem gelir hem gider takip edilir.
    """

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kategori (opsiyonel, silinirse NULL olur)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True
    )

    # Aciklama (ornek: "Ocak ayi kira odemesi")
    description: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    # Tutar: Numeric(12, 2) -> 9,999,999,999.99 TL'ye kadar
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    # Islem tarihi
    expense_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    # Tip: "income" (gelir) veya "expense" (gider)
    expense_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    # Odeme yontemi: nakit, banka, kredi_karti (opsiyonel)
    payment_method: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    # Ek notlar
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    category: Mapped["ExpenseCategory"] = relationship(
        back_populates="expenses"
    )
