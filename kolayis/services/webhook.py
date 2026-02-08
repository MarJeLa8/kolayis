import uuid
import json
import hmac
import hashlib
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from kolayis.models.webhook import Webhook, WebhookLog
from kolayis.schemas.webhook import WebhookCreate, WebhookUpdate

logger = logging.getLogger(__name__)


def get_webhooks(db: Session, owner_id: uuid.UUID) -> list[Webhook]:
    """
    Kullanicinin tum webhook'larini getir.
    En yeni olusturulanlar basta.
    """
    return (
        db.query(Webhook)
        .filter(Webhook.owner_id == owner_id)
        .order_by(Webhook.created_at.desc())
        .all()
    )


def get_webhook(db: Session, webhook_id: uuid.UUID, owner_id: uuid.UUID) -> Webhook | None:
    """
    Belirli bir webhook'u getir.
    Sadece kendi webhook'unu gorebilir (owner_id kontrolu).
    """
    return (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.owner_id == owner_id)
        .first()
    )


def create_webhook(db: Session, owner_id: uuid.UUID, data: WebhookCreate) -> Webhook:
    """
    Yeni webhook olustur.
    events listesini JSON string olarak kaydeder.
    """
    webhook = Webhook(
        owner_id=owner_id,
        url=data.url,
        secret=data.secret,
        events=json.dumps(data.events),  # Liste -> JSON string
        is_active=data.is_active,
        description=data.description,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


def update_webhook(
    db: Session, webhook_id: uuid.UUID, owner_id: uuid.UUID, data: WebhookUpdate
) -> Webhook | None:
    """
    Mevcut webhook'u guncelle.
    Sadece gonderilen (None olmayan) alanlari gunceller.
    """
    webhook = get_webhook(db, webhook_id, owner_id)
    if not webhook:
        return None

    if data.url is not None:
        webhook.url = data.url
    if data.secret is not None:
        webhook.secret = data.secret
    if data.events is not None:
        webhook.events = json.dumps(data.events)
    if data.description is not None:
        webhook.description = data.description
    if data.is_active is not None:
        webhook.is_active = data.is_active

    db.commit()
    db.refresh(webhook)
    return webhook


def delete_webhook(db: Session, webhook_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    """
    Webhook'u sil. Basarili ise True, bulunamazsa False doner.
    Cascade sayesinde ilgili loglar da silinir.
    """
    webhook = get_webhook(db, webhook_id, owner_id)
    if not webhook:
        return False

    db.delete(webhook)
    db.commit()
    return True


def get_webhook_logs(
    db: Session, webhook_id: uuid.UUID, owner_id: uuid.UUID, limit: int = 50
) -> list[WebhookLog]:
    """
    Belirli bir webhook'un log kayitlarini getir.
    Oncelikle webhook'un bu kullaniciya ait oldugunu dogrular.
    En yeni loglar basta, varsayilan limit 50.
    """
    # Webhook sahibi kontrolu
    webhook = get_webhook(db, webhook_id, owner_id)
    if not webhook:
        return []

    return (
        db.query(WebhookLog)
        .filter(WebhookLog.webhook_id == webhook_id)
        .order_by(WebhookLog.sent_at.desc())
        .limit(limit)
        .all()
    )


def fire_webhooks(
    db: Session, owner_id: uuid.UUID, event: str, payload: dict
) -> None:
    """
    Belirli bir olay icin ilgili tum webhook'lari tetikle.

    Isleyis:
    1. Kullanicinin aktif webhook'larini bul
    2. events alaninda bu olayi icerenleri filtrele
    3. Her birine HMAC-SHA256 imzali POST istegi gonder
    4. Sonucu (basari/hata) WebhookLog tablosuna kaydet

    Args:
        db: Veritabani oturumu
        owner_id: Webhook sahibi kullanici
        event: Tetiklenen olay (orn: "invoice.created")
        payload: Gonderilecek veri (dict -> JSON'a cevirilir)
    """
    # Bu kullanicinin aktif webhook'larini al
    webhooks = (
        db.query(Webhook)
        .filter(Webhook.owner_id == owner_id, Webhook.is_active == True)
        .all()
    )

    if not webhooks:
        return

    json_payload = json.dumps(payload, default=str, ensure_ascii=False)

    for webhook in webhooks:
        # Bu webhook bu olayi dinliyor mu?
        try:
            subscribed_events = json.loads(webhook.events)
        except (json.JSONDecodeError, TypeError):
            continue

        if event not in subscribed_events:
            continue

        # HMAC-SHA256 imza hesapla
        signature = hmac.new(
            webhook.secret.encode(),
            json_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # HTTP POST istegi gonder
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event,
        }

        response_status = None
        response_body = None
        success = False
        error_message = None

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    webhook.url,
                    content=json_payload,
                    headers=headers,
                )
                response_status = response.status_code
                # Yanit govdesini sinirlayarak kaydet (cok buyuk olmasin)
                response_body = response.text[:2000] if response.text else None
                success = 200 <= response.status_code < 300

        except httpx.TimeoutException:
            error_message = "Baglanti zaman asimina ugradi (10 saniye)"
            logger.warning(
                f"Webhook timeout: {webhook.url} (event={event})"
            )
        except httpx.ConnectError:
            error_message = "Sunucuya baglanilamadi"
            logger.warning(
                f"Webhook baglanti hatasi: {webhook.url} (event={event})"
            )
        except Exception as e:
            error_message = str(e)[:500]
            logger.error(
                f"Webhook gonderilemedi: {webhook.url} (event={event}): {e}"
            )

        # Sonucu log tablosuna kaydet
        log = WebhookLog(
            webhook_id=webhook.id,
            event=event,
            payload=json_payload,
            response_status=response_status,
            response_body=response_body,
            success=success,
            sent_at=datetime.now(timezone.utc),
            error_message=error_message,
        )
        db.add(log)

    # Tum loglari tek seferde commit et
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Webhook loglari kaydedilemedi: {e}")
        db.rollback()
