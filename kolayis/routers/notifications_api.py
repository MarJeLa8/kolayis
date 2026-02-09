import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.models.user import User
from kolayis.services import notification as notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Kullanicinin bildirimlerini listele."""
    notifications = notification_service.get_notifications(
        db, user.id, unread_only=unread_only, limit=limit, offset=offset
    )
    unread_count = notification_service.get_unread_count(db, user.id)
    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "type_config": notification_service.NOTIFICATION_TYPES.get(
                    n.notification_type, notification_service.NOTIFICATION_TYPES["system"]
                ),
            }
            for n in notifications
        ],
        "unread_count": unread_count,
    }


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Okunmamis bildirim sayisini dondur."""
    count = notification_service.get_unread_count(db, user.id)
    return {"count": count}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek bir bildirimi okundu olarak isaretle."""
    success = notification_service.mark_as_read(db, notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadi")
    return {"success": True}


@router.post("/mark-all-read")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tum bildirimleri okundu olarak isaretle."""
    count = notification_service.mark_all_as_read(db, user.id)
    return {"success": True, "count": count}


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek bir bildirimi sil."""
    success = notification_service.delete_notification(db, notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadi")
    return {"success": True}


@router.delete("/clear-read")
def clear_read_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Okunmus tum bildirimleri sil."""
    count = notification_service.delete_all_read(db, user.id)
    return {"success": True, "count": count}
