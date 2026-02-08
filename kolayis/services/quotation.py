"""
Teklif (Quotation) servis katmani.
Teklif CRUD islemleri, hesaplamalar ve faturaya cevirme islemi.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.quotation import Quotation, QuotationItem
from kolayis.models.invoice import Invoice, InvoiceItem
from kolayis.models.customer import Customer
from kolayis.schemas.quotation import QuotationCreate, QuotationItemCreate, QuotationUpdate
from kolayis.services.activity import log_activity


def _generate_quotation_number(db: Session, owner_id: uuid.UUID) -> str:
    """
    Otomatik teklif numarasi olustur.
    Format: TEK-2026-0001, TEK-2026-0002, ...
    Yil bazli numaralama yapar.
    """
    current_year = datetime.utcnow().year
    # Bu yil icindeki teklif sayisini bul
    count = db.query(func.count(Quotation.id)).filter(
        Quotation.owner_id == owner_id,
        Quotation.quotation_number.like(f"TEK-{current_year}-%"),
    ).scalar()
    return f"TEK-{current_year}-{(count or 0) + 1:04d}"


def _calculate_item(item_data: QuotationItemCreate) -> dict:
    """Teklif kalemi icin toplam ve KDV hesapla."""
    line_total = item_data.quantity * item_data.unit_price
    tax_amount = line_total * Decimal(item_data.tax_rate) / Decimal(100)
    return {
        "line_total": line_total.quantize(Decimal("0.01")),
        "tax_amount": tax_amount.quantize(Decimal("0.01")),
    }


def _recalculate_quotation(quotation: Quotation) -> None:
    """Teklif toplamlarini kalemlerden yeniden hesapla."""
    subtotal = sum(item.line_total for item in quotation.items)
    tax_total = sum(item.tax_amount for item in quotation.items)
    quotation.subtotal = subtotal
    quotation.tax_total = tax_total
    quotation.total = subtotal + tax_total


def get_quotations(
    db: Session, owner_id: uuid.UUID,
    skip: int = 0, limit: int = 20,
    search: str | None = None,
    status_filter: str | None = None,
    sort: str | None = None,
) -> tuple[list[Quotation], int]:
    """
    Teklif listesini sayfalama ile dondur.
    Arama: teklif numarasi veya musteri adinda arar.
    Filtreleme: durum bazinda filtreler.
    Siralama: tarih, gecerlilik veya varsayilan (olusturma).
    Dondurur: (teklif_listesi, toplam_sayi)
    """
    query = db.query(Quotation).filter(Quotation.owner_id == owner_id)

    # Arama filtresi
    if search:
        search_term = f"%{search}%"
        query = query.join(Customer).filter(
            (Quotation.quotation_number.ilike(search_term)) |
            (Customer.company_name.ilike(search_term))
        )

    # Durum filtresi
    if status_filter:
        query = query.filter(Quotation.status == status_filter)

    # Toplam kayit sayisi (sayfalama icin)
    total = query.count()

    # Siralama
    if sort == "date_asc":
        query = query.order_by(Quotation.quotation_date.asc())
    elif sort == "date_desc":
        query = query.order_by(Quotation.quotation_date.desc())
    elif sort == "total_asc":
        query = query.order_by(Quotation.total.asc())
    elif sort == "total_desc":
        query = query.order_by(Quotation.total.desc())
    else:
        query = query.order_by(Quotation.created_at.desc())

    # Sayfalama
    quotations = query.offset(skip).limit(limit).all()

    return quotations, total


def get_quotation(db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID) -> Quotation:
    """Tek bir teklifi getir. Bulunamazsa 404 dondurur."""
    quotation = db.query(Quotation).filter(
        Quotation.id == quotation_id, Quotation.owner_id == owner_id
    ).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teklif bulunamadi"
        )
    return quotation


def create_quotation(db: Session, owner_id: uuid.UUID, data: QuotationCreate) -> Quotation:
    """
    Yeni teklif olustur.
    Otomatik teklif numarasi atar, kalemlerin toplamlarini hesaplar.
    """
    # Musteri kontrolu
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id, Customer.owner_id == owner_id
    ).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi"
        )

    quotation = Quotation(
        owner_id=owner_id,
        customer_id=data.customer_id,
        quotation_number=_generate_quotation_number(db, owner_id),
        quotation_date=data.quotation_date,
        valid_until=data.valid_until,
        status="draft",
        notes=data.notes,
    )

    # Kalemleri ekle
    for item_data in data.items:
        calcs = _calculate_item(item_data)
        item = QuotationItem(
            product_id=item_data.product_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            tax_rate=item_data.tax_rate,
            line_total=calcs["line_total"],
            tax_amount=calcs["tax_amount"],
        )
        quotation.items.append(item)

    _recalculate_quotation(quotation)
    db.add(quotation)
    db.flush()
    log_activity(
        db, owner_id, "create", "quotation", quotation.id,
        f"Teklif '{quotation.quotation_number}' olusturuldu ({customer.company_name})",
    )
    db.commit()
    db.refresh(quotation)
    return quotation


def update_quotation(
    db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID, data: QuotationUpdate
) -> Quotation:
    """
    Teklif bilgilerini guncelle (notlar, gecerlilik tarihi, durum).
    Sadece taslak ve gonderilmis teklifler guncellenebilir.
    """
    quotation = get_quotation(db, quotation_id, owner_id)

    if quotation.status in ("converted",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faturaya cevrilmis teklifler duzenlenemez",
        )

    if data.notes is not None:
        quotation.notes = data.notes
    if data.valid_until is not None:
        quotation.valid_until = data.valid_until
    if data.status is not None:
        old_status = quotation.status
        quotation.status = data.status

        status_labels = {
            "draft": "Taslak", "sent": "Gonderildi",
            "accepted": "Kabul Edildi", "rejected": "Reddedildi",
            "converted": "Faturaya Cevrildi",
        }
        old_label = status_labels.get(old_status, old_status)
        new_label = status_labels.get(data.status, data.status)
        log_activity(
            db, owner_id, "status_change", "quotation", quotation_id,
            f"Teklif '{quotation.quotation_number}' durumu '{old_label}' -> '{new_label}' olarak degistirildi",
        )

    db.commit()
    db.refresh(quotation)
    return quotation


def update_quotation_status(
    db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID, new_status: str
) -> Quotation:
    """Teklif durumunu guncelle."""
    quotation = get_quotation(db, quotation_id, owner_id)
    old_status = quotation.status

    if quotation.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faturaya cevrilmis teklifin durumu degistirilemez",
        )

    quotation.status = new_status

    status_labels = {
        "draft": "Taslak", "sent": "Gonderildi",
        "accepted": "Kabul Edildi", "rejected": "Reddedildi",
        "converted": "Faturaya Cevrildi",
    }
    old_label = status_labels.get(old_status, old_status)
    new_label = status_labels.get(new_status, new_status)
    log_activity(
        db, owner_id, "status_change", "quotation", quotation_id,
        f"Teklif '{quotation.quotation_number}' durumu '{old_label}' -> '{new_label}' olarak degistirildi",
    )
    db.commit()
    db.refresh(quotation)
    return quotation


def delete_quotation(db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    """Teklifi sil. Basarili ise True dondurur."""
    quotation = get_quotation(db, quotation_id, owner_id)

    if quotation.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faturaya cevrilmis teklifler silinemez",
        )

    quotation_number = quotation.quotation_number
    db.delete(quotation)
    log_activity(
        db, owner_id, "delete", "quotation", quotation_id,
        f"Teklif '{quotation_number}' silindi",
    )
    db.commit()
    return True


def add_quotation_item(
    db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID, data: QuotationItemCreate
) -> Quotation:
    """Teklife yeni kalem ekle."""
    quotation = get_quotation(db, quotation_id, owner_id)

    if quotation.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faturaya cevrilmis teklife kalem eklenemez",
        )

    calcs = _calculate_item(data)
    item = QuotationItem(
        quotation_id=quotation_id,
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

    # Teklif toplamini guncelle
    db.refresh(quotation)
    _recalculate_quotation(quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


def remove_quotation_item(
    db: Session, quotation_id: uuid.UUID, item_id: uuid.UUID, owner_id: uuid.UUID
) -> Quotation:
    """Tekliften kalem sil."""
    quotation = get_quotation(db, quotation_id, owner_id)

    if quotation.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faturaya cevrilmis tekliften kalem silinemez",
        )

    item = db.query(QuotationItem).filter(
        QuotationItem.id == item_id, QuotationItem.quotation_id == quotation_id
    ).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teklif kalemi bulunamadi"
        )

    db.delete(item)
    db.flush()

    db.refresh(quotation)
    _recalculate_quotation(quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


def convert_to_invoice(db: Session, quotation_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
    """
    Teklifi faturaya cevir.
    Teklifteki tum kalemleri faturaya kopyalar.
    Teklif durumunu 'converted' yapar.
    Dondurur: olusturulan Invoice nesnesi.
    """
    quotation = get_quotation(db, quotation_id, owner_id)

    if quotation.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu teklif zaten faturaya cevrilmis",
        )

    if not quotation.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bos teklif faturaya cevrilemez",
        )

    # Fatura numarasi olustur (mevcut invoice service pattern'ini kullan)
    from kolayis.services.invoice import _generate_invoice_number

    invoice = Invoice(
        owner_id=owner_id,
        customer_id=quotation.customer_id,
        invoice_number=_generate_invoice_number(db, owner_id),
        invoice_date=date.today(),
        due_date=None,
        status="draft",
        notes=quotation.notes,
    )

    # Teklif kalemlerini fatura kalemlerine kopyala
    for q_item in quotation.items:
        invoice_item = InvoiceItem(
            product_id=q_item.product_id,
            description=q_item.description,
            quantity=q_item.quantity,
            unit_price=q_item.unit_price,
            tax_rate=q_item.tax_rate,
            line_total=q_item.line_total,
            tax_amount=q_item.tax_amount,
        )
        invoice.items.append(invoice_item)

    # Fatura toplamlarini ayarla
    invoice.subtotal = quotation.subtotal
    invoice.tax_total = quotation.tax_total
    invoice.total = quotation.total

    db.add(invoice)
    db.flush()

    # Teklif durumunu guncelle
    quotation.status = "converted"

    # Aktivite loglari
    log_activity(
        db, owner_id, "create", "invoice", invoice.id,
        f"Fatura '{invoice.invoice_number}' teklif '{quotation.quotation_number}' den olusturuldu",
    )
    log_activity(
        db, owner_id, "status_change", "quotation", quotation.id,
        f"Teklif '{quotation.quotation_number}' faturaya cevrildi -> '{invoice.invoice_number}'",
    )

    db.commit()
    db.refresh(invoice)
    return invoice


def get_next_quotation_number(db: Session, owner_id: uuid.UUID) -> str:
    """Siradaki teklif numarasini dondur (onizleme icin)."""
    return _generate_quotation_number(db, owner_id)
