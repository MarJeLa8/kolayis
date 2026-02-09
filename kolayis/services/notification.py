import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from kolayis.models.notification import Notification

logger = logging.getLogger(__name__)

# Bildirim tipi -> ikon ve renk ayarlari (frontend icin)
NOTIFICATION_TYPES = {
    "invoice_paid": {
        "icon": "check-circle",
        "color": "green",
        "label": "Fatura Odendi",
    },
    "invoice_overdue": {
        "icon": "exclamation-circle",
        "color": "red",
        "label": "Vadesi Gecti",
    },
    "invoice_due_soon": {
        "icon": "clock",
        "color": "yellow",
        "label": "Vade Yaklasıyor",
    },
    "payment_received": {
        "icon": "currency-dollar",
        "color": "green",
        "label": "Odeme Alindi",
    },
    "stock_low": {
        "icon": "exclamation-triangle",
        "color": "orange",
        "label": "Stok Azaldi",
    },
    "customer_new": {
        "icon": "user-plus",
        "color": "blue",
        "label": "Yeni Musteri",
    },
    "quotation_accepted": {
        "icon": "thumb-up",
        "color": "green",
        "label": "Teklif Kabul Edildi",
    },
    "recurring_generated": {
        "icon": "refresh",
        "color": "purple",
        "label": "Otomatik Fatura",
    },
    "system": {
        "icon": "information-circle",
        "color": "gray",
        "label": "Sistem",
    },
}


def create_notification(
    db: Session,
    owner_id: uuid.UUID,
    notification_type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    link: str | None = None,
) -> Notification | None:
    """
    Yeni bildirim olustur.
    Hata durumunda sessizce logla, ana islemi engelleme.
    """
    try:
        notification = Notification(
            owner_id=owner_id,
            notification_type=notification_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            link=link,
        )
        db.add(notification)
        db.flush()
        return notification
    except Exception as e:
        logger.error(f"Bildirim olusturulamadi: {e}")
        return None


def get_notifications(
    db: Session,
    owner_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> list[Notification]:
    """Kullanicinin bildirimlerini getir."""
    query = db.query(Notification).filter(Notification.owner_id == owner_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session, owner_id: uuid.UUID) -> int:
    """Okunmamis bildirim sayisini dondur."""
    return (
        db.query(Notification)
        .filter(Notification.owner_id == owner_id, Notification.is_read == False)
        .count()
    )


def mark_as_read(
    db: Session, notification_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """Tek bir bildirimi okundu olarak isaretle."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.owner_id == owner_id,
        )
        .first()
    )
    if not notification:
        return False
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    return True


def mark_all_as_read(db: Session, owner_id: uuid.UUID) -> int:
    """Tum bildirimleri okundu yap. Etkilenen satir sayisini dondur."""
    count = (
        db.query(Notification)
        .filter(
            Notification.owner_id == owner_id,
            Notification.is_read == False,
        )
        .update(
            {"is_read": True, "read_at": datetime.now(timezone.utc)},
            synchronize_session="fetch",
        )
    )
    db.commit()
    return count


def delete_notification(
    db: Session, notification_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """Tek bir bildirimi sil."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.owner_id == owner_id,
        )
        .first()
    )
    if not notification:
        return False
    db.delete(notification)
    db.commit()
    return True


def delete_all_read(db: Session, owner_id: uuid.UUID) -> int:
    """Okunmus tum bildirimleri sil."""
    count = (
        db.query(Notification)
        .filter(
            Notification.owner_id == owner_id,
            Notification.is_read == True,
        )
        .delete(synchronize_session="fetch")
    )
    db.commit()
    return count
