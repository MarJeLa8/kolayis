import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Product(Base):
    """
    Urun/Hizmet modeli.
    Satilan urunleri veya sunulan hizmetleri temsil eder.
    Fatura olusturulurken bu urunler secilir.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Urun bilgileri
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Birim fiyat (ornek: 150.00 TL)
    # Numeric(10, 2) = toplam 10 basamak, 2'si ondalik
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    # Birim (adet, saat, kg, metre vs.)
    unit: Mapped[str] = mapped_column(
        String(20), default="adet"
    )
    # KDV orani (yuzde olarak, ornek: 20 = %20)
    tax_rate: Mapped[int] = mapped_column(
        Integer, default=20
    )
    # Stok miktari (opsiyonel, hizmetler icin null)
    stock: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliski
    owner: Mapped["User"] = relationship()
