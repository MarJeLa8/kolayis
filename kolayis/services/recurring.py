"""
Tekrarlayan fatura servisi.
CRUD islemleri, fatura uretimi ve zamanlama mantigi burada.
"""

import uuid
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.recurring import RecurringInvoice, RecurringInvoiceItem
from kolayis.models.customer import Customer
from kolayis.models.invoice import Invoice, InvoiceItem
from kolayis.schemas.recurring import RecurringCreate, RecurringUpdate
from kolayis.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from kolayis.services.invoice import create_invoice
from kolayis.services.activity import log_activity

logger = logging.getLogger(__name__)


def _calculate_next_run_date(current_date: date, frequency: str) -> date:
    """
    Mevcut tarihten sonraki calisma tarihini hesapla.
    frequency: weekly, monthly, quarterly, yearly
    """
    if frequency == "weekly":
        return current_date + timedelta(weeks=1)
    elif frequency == "monthly":
        return current_date + relativedelta(months=1)
    elif frequency == "quarterly":
        return current_date + relativedelta(months=3)
    elif frequency == "yearly":
        return current_date + relativedelta(years=1)
    else:
        # Bilinmeyen siklik - aylik olarak varsay
        return current_date + relativedelta(months=1)


def get_recurring_invoices(
    db: Session,
    owner_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    is_active_filter: bool | None = None,
) -> list[RecurringInvoice]:
    """
    Tekrarlayan fatura listesini getir.
    is_active_filter: True=sadece aktifler, False=sadece pasifler, None=hepsi
    """
    query = db.query(RecurringInvoice).filter(
        RecurringInvoice.owner_id == owner_id
    )
    if is_active_filter is not None:
        query = query.filter(RecurringInvoice.is_active == is_active_filter)

    return (
        query.order_by(RecurringInvoice.next_run_date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_recurring_invoice(
    db: Session, recurring_id: uuid.UUID, owner_id: uuid.UUID
) -> RecurringInvoice | None:
    """Tek bir tekrarlayan faturayi getir."""
    return db.query(RecurringInvoice).filter(
        RecurringInvoice.id == recurring_id,
        RecurringInvoice.owner_id == owner_id,
    ).first()


def create_recurring_invoice(
    db: Session, owner_id: uuid.UUID, data: RecurringCreate
) -> RecurringInvoice:
    """
    Yeni tekrarlayan fatura olustur.
    Musteri kontrolu yapar, kalemleri ekler.
    """
    # Musteri kontrolu
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id, Customer.owner_id == owner_id
    ).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi"
        )

    recurring = RecurringInvoice(
        owner_id=owner_id,
        customer_id=data.customer_id,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        next_run_date=data.start_date,  # Ilk calisma tarihi = baslangic tarihi
        is_active=True,
        notes=data.notes,
    )

    # Kalemleri ekle
    for item_data in data.items:
        item = RecurringInvoiceItem(
            product_id=item_data.product_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            tax_rate=item_data.tax_rate,
        )
        recurring.items.append(item)

    db.add(recurring)
    db.flush()

    log_activity(
        db, owner_id, "create", "recurring_invoice", recurring.id,
        f"Tekrarlayan fatura olusturuldu ({customer.company_name}, {recurring.frequency_label})",
    )
    db.commit()
    db.refresh(recurring)
    return recurring


def update_recurring_invoice(
    db: Session,
    recurring_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: RecurringUpdate,
) -> RecurringInvoice | None:
    """Tekrarlayan fatura bilgilerini guncelle."""
    recurring = get_recurring_invoice(db, recurring_id, owner_id)
    if not recurring:
        return None

    if data.frequency is not None:
        recurring.frequency = data.frequency
    if data.end_date is not None:
        recurring.end_date = data.end_date
    if data.is_active is not None:
        recurring.is_active = data.is_active
    if data.notes is not None:
        recurring.notes = data.notes

    log_activity(
        db, owner_id, "update", "recurring_invoice", recurring.id,
        f"Tekrarlayan fatura guncellendi ({recurring.customer.company_name})",
    )
    db.commit()
    db.refresh(recurring)
    return recurring


def delete_recurring_invoice(
    db: Session, recurring_id: uuid.UUID, owner_id: uuid.UUID
) -> bool:
    """Tekrarlayan faturayi sil."""
    recurring = get_recurring_invoice(db, recurring_id, owner_id)
    if not recurring:
        return False

    customer_name = recurring.customer.company_name
    db.delete(recurring)
    log_activity(
        db, owner_id, "delete", "recurring_invoice", recurring_id,
        f"Tekrarlayan fatura silindi ({customer_name})",
    )
    db.commit()
    return True


def toggle_active(
    db: Session, recurring_id: uuid.UUID, owner_id: uuid.UUID
) -> RecurringInvoice | None:
    """Tekrarlayan faturayi aktif/pasif yap."""
    recurring = get_recurring_invoice(db, recurring_id, owner_id)
    if not recurring:
        return None

    recurring.is_active = not recurring.is_active
    new_status = "aktif" if recurring.is_active else "pasif"

    log_activity(
        db, owner_id, "update", "recurring_invoice", recurring.id,
        f"Tekrarlayan fatura {new_status} yapildi ({recurring.customer.company_name})",
    )
    db.commit()
    db.refresh(recurring)
    return recurring


def generate_invoice_from_recurring(
    db: Session, recurring: RecurringInvoice
) -> Invoice:
    """
    Tekrarlayan faturadan normal bir fatura olustur.
    Kalemleri kopyalar, next_run_date'i ilerletir, total_generated'i arttirir.
    """
    # Fatura kalemleri olustur (recurring item -> invoice item)
    invoice_items = []
    for item in recurring.items:
        invoice_items.append(
            InvoiceItemCreate(
                product_id=item.product_id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
            )
        )

    # Fatura olustur (mevcut invoice service'i kullan)
    today = date.today()
    invoice_data = InvoiceCreate(
        customer_id=recurring.customer_id,
        invoice_date=today,
        due_date=today + timedelta(days=30),  # Varsayilan 30 gun vade
        status="draft",
        notes=f"Tekrarlayan faturadan otomatik olusturuldu ({recurring.frequency_label})",
        items=invoice_items,
    )

    invoice = create_invoice(db, recurring.owner_id, invoice_data)

    # Tekrarlayan fatura bilgilerini guncelle
    recurring.last_generated_at = datetime.utcnow()
    recurring.total_generated += 1
    recurring.next_run_date = _calculate_next_run_date(
        recurring.next_run_date, recurring.frequency
    )

    # Bitis tarihi kontrolu: eger next_run_date bitis tarihini gecmisse pasif yap
    if recurring.end_date and recurring.next_run_date > recurring.end_date:
        recurring.is_active = False

    db.commit()
    db.refresh(recurring)

    logger.info(
        "Tekrarlayan fatura %s icin fatura %s olusturuldu",
        recurring.id, invoice.invoice_number,
    )
    return invoice


def process_due_recurring(db: Session) -> int:
    """
    Vadesi gelmis tum tekrarlayan faturalari isle.
    Bugun veya daha eski next_run_date'e sahip aktif tekrarlayan faturalar icin
    otomatik fatura olusturur.
    Kac fatura olusturuldugunu dondurur.
    """
    today = date.today()
    due_recurring = (
        db.query(RecurringInvoice)
        .filter(
            RecurringInvoice.is_active == True,
            RecurringInvoice.next_run_date <= today,
        )
        .all()
    )

    generated_count = 0
    for recurring in due_recurring:
        # Bitis tarihi kontrolu
        if recurring.end_date and today > recurring.end_date:
            recurring.is_active = False
            db.commit()
            continue

        try:
            generate_invoice_from_recurring(db, recurring)
            generated_count += 1
        except Exception as e:
            logger.error(
                "Tekrarlayan fatura %s icin fatura olusturulamadi: %s",
                recurring.id, str(e),
            )
            # Hata durumunda diger tekrarlayan faturalara devam et
            continue

    logger.info("Toplam %d tekrarlayan fatura islendi", generated_count)
    return generated_count
