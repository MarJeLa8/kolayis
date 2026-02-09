"""
WhatsApp Business API servisi.
Meta Cloud API uzerinden mesaj gonderme.
"""
import uuid
import logging
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from kolayis.config import settings
from kolayis.models.whatsapp_message import WhatsAppMessage
from kolayis.models.invoice import Invoice
from kolayis.models.customer import Customer

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"


def _normalize_phone(phone: str) -> str:
    """Telefon numarasini WhatsApp formatina cevir (90XXXXXXXXXX)."""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "90" + phone[1:]
    if not phone.startswith("90") and len(phone) == 10:
        phone = "90" + phone
    return phone


def _send_whatsapp_message(phone: str, message: str) -> dict:
    """WhatsApp Cloud API ile mesaj gonder."""
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        return {"success": False, "error": "WhatsApp API yapilandirilmamis"}

    normalized = _normalize_phone(phone)

    try:
        resp = httpx.post(
            f"{WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": normalized,
                "type": "text",
                "text": {"body": message},
            },
            timeout=15,
        )
        result = resp.json()

        if resp.status_code == 200 and "messages" in result:
            wa_id = result["messages"][0].get("id", "")
            return {"success": True, "wa_message_id": wa_id}
        else:
            error = result.get("error", {}).get("message", "Bilinmeyen hata")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"WhatsApp mesaj gonderme hatasi: {e}")
        return {"success": False, "error": str(e)}


def send_invoice(
    db: Session, owner_id: uuid.UUID,
    invoice: Invoice, customer: Customer,
) -> WhatsAppMessage:
    """Fatura bilgisini WhatsApp ile gonder."""
    if not customer.phone:
        msg = WhatsAppMessage(
            owner_id=owner_id, customer_id=customer.id,
            invoice_id=invoice.id, phone_number="",
            message_type="invoice_send", message_body="",
            status="failed", error_message="Musteri telefon numarasi yok",
        )
        db.add(msg)
        db.commit()
        return msg

    message = (
        f"Sayin {customer.contact_name or customer.company_name},\n\n"
        f"Fatura bilgileriniz:\n"
        f"Fatura No: {invoice.invoice_number}\n"
        f"Toplam: {invoice.total:.2f} TL\n"
        f"Vade: {invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '-'}\n"
    )
    if invoice.remaining_amount > 0:
        message += f"Kalan Borc: {invoice.remaining_amount:.2f} TL\n"
    message += f"\nKolayIS - {settings.APP_NAME}"

    wa_msg = WhatsAppMessage(
        owner_id=owner_id, customer_id=customer.id,
        invoice_id=invoice.id, phone_number=customer.phone,
        message_type="invoice_send", message_body=message,
    )
    db.add(wa_msg)
    db.flush()

    result = _send_whatsapp_message(customer.phone, message)
    if result["success"]:
        wa_msg.status = "sent"
        wa_msg.wa_message_id = result.get("wa_message_id")
    else:
        wa_msg.status = "failed"
        wa_msg.error_message = result.get("error")

    db.commit()
    db.refresh(wa_msg)
    return wa_msg


def send_payment_reminder(
    db: Session, owner_id: uuid.UUID,
    invoice: Invoice, customer: Customer,
) -> WhatsAppMessage:
    """Odeme hatirlatmasi gonder."""
    if not customer.phone:
        msg = WhatsAppMessage(
            owner_id=owner_id, customer_id=customer.id,
            invoice_id=invoice.id, phone_number="",
            message_type="payment_reminder", message_body="",
            status="failed", error_message="Musteri telefon numarasi yok",
        )
        db.add(msg)
        db.commit()
        return msg

    overdue_text = ""
    if invoice.due_date:
        from datetime import date
        if invoice.due_date < date.today():
            days = (date.today() - invoice.due_date).days
            overdue_text = f"\n(Vade tarihi {days} gun once gecmistir)\n"

    message = (
        f"Sayin {customer.contact_name or customer.company_name},\n\n"
        f"Odeme hatirlatmasi:\n"
        f"Fatura No: {invoice.invoice_number}\n"
        f"Kalan Borc: {invoice.remaining_amount:.2f} TL\n"
        f"Vade: {invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '-'}\n"
        f"{overdue_text}"
        f"\nOdemenizi en kisa surede yapmanizi rica ederiz.\n"
        f"KolayIS - {settings.APP_NAME}"
    )

    wa_msg = WhatsAppMessage(
        owner_id=owner_id, customer_id=customer.id,
        invoice_id=invoice.id, phone_number=customer.phone,
        message_type="payment_reminder", message_body=message,
    )
    db.add(wa_msg)
    db.flush()

    result = _send_whatsapp_message(customer.phone, message)
    if result["success"]:
        wa_msg.status = "sent"
        wa_msg.wa_message_id = result.get("wa_message_id")
    else:
        wa_msg.status = "failed"
        wa_msg.error_message = result.get("error")

    db.commit()
    db.refresh(wa_msg)
    return wa_msg


def send_custom_message(
    db: Session, owner_id: uuid.UUID,
    customer: Customer, message_text: str,
) -> WhatsAppMessage:
    """Serbest metin mesaji gonder."""
    if not customer.phone:
        msg = WhatsAppMessage(
            owner_id=owner_id, customer_id=customer.id,
            phone_number="", message_type="custom",
            message_body=message_text,
            status="failed", error_message="Musteri telefon numarasi yok",
        )
        db.add(msg)
        db.commit()
        return msg

    wa_msg = WhatsAppMessage(
        owner_id=owner_id, customer_id=customer.id,
        phone_number=customer.phone,
        message_type="custom", message_body=message_text,
    )
    db.add(wa_msg)
    db.flush()

    result = _send_whatsapp_message(customer.phone, message_text)
    if result["success"]:
        wa_msg.status = "sent"
        wa_msg.wa_message_id = result.get("wa_message_id")
    else:
        wa_msg.status = "failed"
        wa_msg.error_message = result.get("error")

    db.commit()
    db.refresh(wa_msg)
    return wa_msg


def get_message_history(
    db: Session, owner_id: uuid.UUID,
    customer_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[WhatsAppMessage]:
    """Mesaj gecmisini getir."""
    query = db.query(WhatsAppMessage).filter(WhatsAppMessage.owner_id == owner_id)
    if customer_id:
        query = query.filter(WhatsAppMessage.customer_id == customer_id)
    return query.order_by(WhatsAppMessage.created_at.desc()).limit(limit).all()
