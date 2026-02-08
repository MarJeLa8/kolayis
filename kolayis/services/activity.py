import uuid
import logging

from sqlalchemy.orm import Session

from kolayis.models.activity import Activity

logger = logging.getLogger(__name__)


def log_activity(
    db: Session,
    owner_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    description: str,
) -> Activity:
    """
    Aktivite logu kaydet.
    Herhangi bir hata olursa sessizce logla, ana islemi engelleme.

    Args:
        db: Veritabani oturumu
        owner_id: Islemi yapan kullanicinin ID'si
        action: Islem turu (create, update, delete, status_change)
        entity_type: Varlik tipi (customer, product, invoice, payment)
        entity_id: Isleme konu olan varligin ID'si
        description: Insan tarafindan okunabilir aciklama
    """
    try:
        activity = Activity(
            owner_id=owner_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )
        db.add(activity)
        db.flush()  # Ana commit service tarafindan yapilacak, biz sadece flush yapariz
        return activity
    except Exception as e:
        logger.error(f"Aktivite logu kaydedilemedi: {e}")
        return None


def get_recent_activities(
    db: Session, owner_id: uuid.UUID, limit: int = 20
) -> list[Activity]:
    """
    Kullanicinin son aktivitelerini getir.
    En yeniden en eskiye siralanir.
    """
    return (
        db.query(Activity)
        .filter(Activity.owner_id == owner_id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )


def get_activities_paginated(
    db: Session, owner_id: uuid.UUID, page: int = 1, size: int = 20,
    action: str | None = None, entity_type: str | None = None,
) -> tuple[list[Activity], int]:
    """
    Kullanicinin aktivitelerini sayfalama ile getir.
    Filtreleme destekler: islem turu ve varlik tipi.
    Dondurur: (aktivite_listesi, toplam_sayi)
    """
    query = db.query(Activity).filter(Activity.owner_id == owner_id)

    if action:
        query = query.filter(Activity.action == action)
    if entity_type:
        query = query.filter(Activity.entity_type == entity_type)

    total = query.count()

    offset = (page - 1) * size
    activities = (
        query.order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return activities, total
