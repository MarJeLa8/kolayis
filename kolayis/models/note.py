import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from kolayis.database import Base


class Note(Base):
    """
    Gorusme notu modeli.
    Musterilerle yapilan gorusmelerin kaydi.
    Her not bir musteriye ve bir yazara (kullanici) aittir.
    """

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    # Hangi musteriye ait?
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Notu kim yazdi?
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Not bilgileri
    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    # Gorusme tipi: phone (telefon), email, meeting (toplanti), other (diger)
    note_type: Mapped[str] = mapped_column(
        String(20), default="other"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Iliskiler
    customer: Mapped["Customer"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship()
