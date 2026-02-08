import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class User(Base):
    """
    Kullanici modeli.
    Sisteme kayit olan ve giris yapan kullanicilari temsil eder.
    Her kullanicinin kendi musterileri vardir.
    """

    __tablename__ = "users"

    # Primary key: UUID kullaniyoruz (tahmin edilemez, guvenli)
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    # Email: benzersiz olmali, index ile hizli arama
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # Sifre: hashlenmiş hali saklanir, asla duz metin degil!
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Kullanicinin tam adi
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Aktif mi? (Hesap kapatildiysa False yapilir)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    # Kullanici rolu: admin, manager, user
    # Yeni kayit olan kullanicilar "user" rolunde baslar
    role: Mapped[str] = mapped_column(
        String(20), default="user"
    )

    # Email dogrulama alanlari
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    verification_code: Mapped[str | None] = mapped_column(
        String(6), nullable=True
    )
    verification_code_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 2FA: TOTP secret (None = 2FA kapali)
    totp_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Olusturulma ve guncellenme tarihleri
    # server_default=func.now() -> veritabani tarafinda otomatik atanir
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliski: Bu kullanicinin musterileri
    # cascade="all, delete-orphan" -> kullanici silinirse musterileri de silinir
    customers: Mapped[list["Customer"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
