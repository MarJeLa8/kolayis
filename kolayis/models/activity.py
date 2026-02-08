import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Activity(Base):
    """
    Aktivite logu modeli.
    Kullanicilarin CRM uzerindeki islemlerini kaydeder.
    Ornek: musteri olusturma, fatura silme, urun guncelleme vb.
    """

    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    # Bu aktiviteyi yapan kullanici
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Islem turu: create, update, delete, login, status_change
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # Hangi varlik tipi uzerinde islem yapildi: customer, product, invoice, payment
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # Isleme konu olan varligin ID'si (silinmis olabilir, nullable)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )
    # Insan tarafindan okunabilir aciklama: "Musteri 'ABC Ltd' olusturuldu"
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliski
    owner: Mapped["User"] = relationship()
