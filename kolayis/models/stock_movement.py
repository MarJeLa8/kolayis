import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class StockMovement(Base):
    """
    Stok hareketi modeli.
    Urunlerin stok giris, cikis ve duzeltme hareketlerini takip eder.
    Her hareket onceki ve yeni stok degerlerini kaydeder (audit trail).
    """

    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    # Hareket tipi: "in" (giris), "out" (cikis), "adjustment" (duzeltme)
    movement_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    # Miktar (her zaman pozitif sayi olarak saklanir)
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # Referans bilgisi: bu hareket nereden geldi?
    # reference_type: "invoice" (fatura kaynakli), "manual" (elle giris), "import" (toplu aktarim)
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    # Referans ID: ornegin fatura ID'si
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )

    # Aciklama / not
    notes: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Stok degerleri: hareket oncesi ve sonrasi (audit trail)
    previous_stock: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    new_stock: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliskiler
    owner: Mapped["User"] = relationship()
    product: Mapped["Product"] = relationship()

    # Indexler: urun bazli ve tarih bazli sorgular icin
    __table_args__ = (
        Index("ix_stock_movements_product_id", "product_id"),
        Index("ix_stock_movements_created_at", "created_at"),
    )
