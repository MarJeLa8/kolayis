import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Customer(Base):
    """
    Musteri modeli.
    CRM'deki musterileri temsil eder.
    Her musteri bir kullaniciya (owner) aittir.
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    # Bu musteri hangi kullaniciya ait?
    # ForeignKey: users tablosundaki id'ye referans verir
    # ondelete="CASCADE": kullanici silinirse musterileri de silinir
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Musteri bilgileri
    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    address: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Vergi numarasi (Turkiye'de onemli)
    tax_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    # Musteri durumu: active, inactive, lead (potansiyel)
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship(back_populates="customers")
    notes: Mapped[list["Note"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
