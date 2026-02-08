"""
Musteri Portali erisim modeli.
Musterilerin kendi faturalarini gorup odeme durumunu takip edebilmesi icin
ayri bir giris sistemi saglar.

Her musteriye benzersiz bir erisim kodu (access_token) ve PIN atanir.
Musteri portale giris yapmak icin bu iki bilgiyi kullanir.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class PortalAccess(Base):
    """
    Musteri portal erisim modeli.
    Her musterinin tek bir portal erisimi olabilir (customer_id unique).
    access_token: musteriye verilen benzersiz erisim kodu
    pin_hash: 4-6 haneli PIN'in hashlenmis hali
    """

    __tablename__ = "portal_access"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    # Bu portal erisimi hangi musteriye ait?
    # unique=True: her musterinin sadece bir portal erisimi olabilir
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Benzersiz erisim kodu (secrets.token_urlsafe ile uretilir)
    access_token: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    # PIN'in hashlenmis hali (4-6 haneli sayi)
    pin_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Erisim aktif mi?
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    # Son giris zamani
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Iliskiler - polimorfik iliski: Customer modeline dokunmadan baglanti
    customer: Mapped["Customer"] = relationship()
