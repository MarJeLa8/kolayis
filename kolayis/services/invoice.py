import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.invoice import Invoice, InvoiceItem
from kolayis.models.customer import Customer
from kolayis.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceUpdate
from kolayis.services.activity import log_activity


def _generate_invoice_number(db: Session, owner_id: uuid.UUID) -> str:
    """
    Otomatik fatura numarasi olustur.
    Format: FTR-0001, FTR-0002, ...
    """
    count = db.query(func.count(Invoice.id)).filter(
        Invoice.owner_id == owner_id
    ).scalar()
    return f"FTR-{(count or 0) + 1:04d}"


def _calculate_item(item_data: InvoiceItemCreate) -> dict:
    """Fatura kalemi icin toplam ve KDV hesapla."""
    line_total = item_data.quantity * item_data.unit_price
    tax_amount = line_total * Decimal(item_data.tax_rate) / Decimal(100)
    return {
        "line_total": line_total.quantize(Decimal("0.01")),
        "tax_amount": tax_amount.quantize(Decimal("0.01")),
    }


def _recalculate_invoice(invoice: Invoice) -> None:
    """Fatura toplamlarini kalemlerden yeniden hesapla."""
    subtotal = sum(item.line_total for item in invoice.items)
    tax_total = sum(item.tax_amount for item in invoice.items)
    invoice.subtotal = subtotal
    invoice.tax_total = tax_total
    invoice.total = subtotal + tax_total


def get_invoices(
    db: Session, owner_id: uuid.UUID, customer_id: uuid.UUID | None = None,
    invoice_status: str | None = None,
    page: int = 1, size: int = 20,
    sort: str | None = None,
) -> tuple[list[Invoice], int]:
    """
    Fatura listesini sayfalama ile dondur.
    sort parametresi: 'due_date_asc', 'due_date_desc' destekler.
    Dondurur: (fatura_listesi, toplam_sayi)
    """
    query = db.query(Invoice).filter(Invoice.owner_id == owner_id)
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
    if invoice_status:
        query = query.filter(Invoice.status == invoice_status)

    # Toplam kayit sayisi (sayfalama icin)
    total = query.count()

    # Siralama
    if sort == "due_date_asc":
        # NULL vade tarihlerini sona at
        from sqlalchemy import case, asc
        query = query.order_by(
            case((Invoice.due_date.is_(None), 1), else_=0),
            Invoice.due_date.asc(),
        )
    elif sort == "due_date_desc":
        from sqlalchemy import case, desc
        query = query.order_by(
            case((Invoice.due_date.is_(None), 1), else_=0),
            Invoice.due_date.desc(),
        )
    else:
        query = query.order_by(Invoice.created_at.desc())

    # Sayfalama: OFFSET ve LIMIT ile
    offset = (page - 1) * size
    invoices = query.offset(offset).limit(size).all()

    return invoices, total


def get_invoice(db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.owner_id == owner_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura bulunamadi")
    return invoice


def create_invoice(db: Session, owner_id: uuid.UUID, data: InvoiceCreate) -> Invoice:
    # Musteri kontrolu
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id, Customer.owner_id == owner_id
    ).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    invoice = Invoice(
        owner_id=owner_id,
        customer_id=data.customer_id,
        invoice_number=_generate_invoice_number(db, owner_id),
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        status=data.status,
        notes=data.notes,
    )

    # Kalemleri ekle
    for item_data in data.items:
        calcs = _calculate_item(item_data)
        item = InvoiceItem(
            product_id=item_data.product_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            tax_rate=item_data.tax_rate,
            line_total=calcs["line_total"],
            tax_amount=calcs["tax_amount"],
        )
        invoice.items.append(item)

    _recalculate_invoice(invoice)
    db.add(invoice)
    db.flush()
    log_activity(
        db, owner_id, "create", "invoice", invoice.id,
        f"Fatura '{invoice.invoice_number}' olusturuldu ({customer.company_name})",
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def add_invoice_item(
    db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID, data: InvoiceItemCreate
) -> Invoice:
    invoice = get_invoice(db, invoice_id, owner_id)

    calcs = _calculate_item(data)
    item = InvoiceItem(
        invoice_id=invoice_id,
        product_id=data.product_id,
        description=data.description,
        quantity=data.quantity,
        unit_price=data.unit_price,
        tax_rate=data.tax_rate,
        line_total=calcs["line_total"],
        tax_amount=calcs["tax_amount"],
    )
    db.add(item)
    db.flush()

    # Fatura toplamini guncelle
    db.refresh(invoice)
    _recalculate_invoice(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def remove_invoice_item(
    db: Session, invoice_id: uuid.UUID, item_id: uuid.UUID, owner_id: uuid.UUID
) -> Invoice:
    invoice = get_invoice(db, invoice_id, owner_id)

    item = db.query(InvoiceItem).filter(
        InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura kalemi bulunamadi")

    db.delete(item)
    db.flush()

    db.refresh(invoice)
    _recalculate_invoice(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(
    db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID, data: InvoiceUpdate
) -> Invoice:
    """Fatura bilgilerini guncelle (musteri, tarih, vade, notlar)."""
    invoice = get_invoice(db, invoice_id, owner_id)

    if invoice.status not in ("draft", "sent"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sadece taslak ve gonderilmis faturalar duzenlenebilir",
        )

    # Musteri kontrolu
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id, Customer.owner_id == owner_id
    ).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    invoice.customer_id = data.customer_id
    invoice.invoice_date = data.invoice_date
    invoice.due_date = data.due_date
    invoice.notes = data.notes

    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_status(
    db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID, new_status: str
) -> Invoice:
    invoice = get_invoice(db, invoice_id, owner_id)
    old_status = invoice.status
    invoice.status = new_status

    status_labels = {
        "draft": "Taslak", "sent": "Gonderildi",
        "paid": "Odendi", "cancelled": "Iptal",
    }
    old_label = status_labels.get(old_status, old_status)
    new_label = status_labels.get(new_status, new_status)
    log_activity(
        db, owner_id, "status_change", "invoice", invoice_id,
        f"Fatura '{invoice.invoice_number}' durumu '{old_label}' -> '{new_label}' olarak degistirildi",
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    invoice = get_invoice(db, invoice_id, owner_id)
    invoice_number = invoice.invoice_number
    db.delete(invoice)
    log_activity(
        db, owner_id, "delete", "invoice", invoice_id,
        f"Fatura '{invoice_number}' silindi",
    )
    db.commit()


def get_monthly_revenue(db: Session, owner_id: uuid.UUID, months: int = 6) -> list[dict]:
    """
    Son N ayin aylik gelir verisi (odenmis faturalardan).
    Dondurur: [{"month": "2026-01", "revenue": 15000.00}, ...]
    """
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    start = now.replace(day=1) - timedelta(days=30 * (months - 1))
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            func.to_char(Invoice.invoice_date, 'YYYY-MM').label('month'),
            func.coalesce(func.sum(Invoice.total), 0).label('revenue'),
        )
        .filter(
            Invoice.owner_id == owner_id,
            Invoice.status == 'paid',
            Invoice.invoice_date >= start,
        )
        .group_by(func.to_char(Invoice.invoice_date, 'YYYY-MM'))
        .order_by(func.to_char(Invoice.invoice_date, 'YYYY-MM'))
        .all()
    )
    return [{"month": r.month, "revenue": float(r.revenue)} for r in rows]


def get_invoice_stats(db: Session, owner_id: uuid.UUID) -> dict:
    """Fatura istatistikleri."""
    invoices = db.query(Invoice).filter(Invoice.owner_id == owner_id).all()
    total_count = len(invoices)
    total_revenue = sum(i.total for i in invoices)
    paid_total = sum(i.total for i in invoices if i.status == "paid")
    unpaid_total = sum(i.total for i in invoices if i.status in ("draft", "sent"))

    by_status = {}
    for i in invoices:
        by_status[i.status] = by_status.get(i.status, 0) + 1

    return {
        "total_count": total_count,
        "total_revenue": total_revenue,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "by_status": by_status,
    }
