"""
Takvim veri servisi.
Belirli bir aydaki fatura, vade, odeme ve teklif tarihlerini
takvim gorunumu icin uygun formatta dondurur.
"""
import uuid
import calendar
from datetime import date

from sqlalchemy.orm import Session

from kolayis.models.invoice import Invoice
from kolayis.models.payment import Payment


def get_calendar_events(
    db: Session, owner_id: uuid.UUID, year: int, month: int
) -> list[dict]:
    """
    Belirli bir aydaki tum takvim etkinliklerini getir.

    Etkinlik tipleri:
        - invoice_date: Faturanin kesildigi tarih (mavi)
        - invoice_due: Faturanin vade tarihi (kirmizi)
        - payment_date: Odeme yapildigi tarih (mor)
        - quote_date: Teklif/taslak fatura tarihi (yesil)

    Her etkinlik formati:
        {
            "date": "2026-02-15",
            "type": "invoice_due",
            "title": "FTR-001 vade",
            "color": "#ef4444",
            "url": "/invoices/uuid"
        }

    Args:
        db: Veritabani oturumu
        owner_id: Kullanici ID
        year: Yil (ornek: 2026)
        month: Ay (1-12)

    Returns:
        Etkinlik listesi (list[dict])
    """
    events = []

    # Ayin ilk ve son gunu
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    # Renk tanimlari
    colors = {
        "invoice_date": "#3b82f6",   # mavi
        "invoice_due": "#ef4444",     # kirmizi
        "quote_date": "#22c55e",      # yesil
        "payment_date": "#a855f7",    # mor
    }

    # --- 1. Fatura tarihleri (kesilme tarihi) ---
    # Durum: sent veya paid olan faturalar
    invoices_by_date = (
        db.query(Invoice)
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.invoice_date >= first_day,
            Invoice.invoice_date <= last_day,
            Invoice.status.in_(["sent", "paid"]),
        )
        .all()
    )

    for inv in invoices_by_date:
        events.append({
            "date": inv.invoice_date.isoformat(),
            "type": "invoice_date",
            "title": f"{inv.invoice_number} fatura",
            "color": colors["invoice_date"],
            "url": f"/invoices/{inv.id}",
        })

    # --- 2. Vade tarihleri ---
    # Vade tarihi bu ay icinde olan tum faturalar (iptal haric)
    invoices_by_due = (
        db.query(Invoice)
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.due_date >= first_day,
            Invoice.due_date <= last_day,
            Invoice.due_date.isnot(None),
            Invoice.status.in_(["draft", "sent", "paid"]),
        )
        .all()
    )

    for inv in invoices_by_due:
        events.append({
            "date": inv.due_date.isoformat(),
            "type": "invoice_due",
            "title": f"{inv.invoice_number} vade",
            "color": colors["invoice_due"],
            "url": f"/invoices/{inv.id}",
        })

    # --- 3. Teklif tarihleri (taslak faturalar) ---
    # Taslak durumundaki faturalarin kesilme tarihi teklif olarak gosterilir
    draft_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.invoice_date >= first_day,
            Invoice.invoice_date <= last_day,
            Invoice.status == "draft",
        )
        .all()
    )

    for inv in draft_invoices:
        events.append({
            "date": inv.invoice_date.isoformat(),
            "type": "quote_date",
            "title": f"{inv.invoice_number} teklif",
            "color": colors["quote_date"],
            "url": f"/invoices/{inv.id}",
        })

    # --- 4. Odeme tarihleri ---
    # Bu aydaki odemeler (fatura uzerinden owner kontrolu)
    payments = (
        db.query(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(
            Invoice.owner_id == owner_id,
            Payment.payment_date >= first_day,
            Payment.payment_date <= last_day,
        )
        .all()
    )

    for pay in payments:
        # Odemenin ait oldugu fatura bilgisini al
        invoice = db.query(Invoice).filter(Invoice.id == pay.invoice_id).first()
        inv_number = invoice.invoice_number if invoice else "?"
        inv_id = str(invoice.id) if invoice else ""

        events.append({
            "date": pay.payment_date.isoformat(),
            "type": "payment_date",
            "title": f"{inv_number} odeme ({pay.amount:.0f} TL)",
            "color": colors["payment_date"],
            "url": f"/invoices/{inv_id}" if inv_id else "#",
        })

    # Tarihe gore sirala
    events.sort(key=lambda e: e["date"])

    return events
