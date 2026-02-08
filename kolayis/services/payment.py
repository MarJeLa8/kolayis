import uuid
from decimal import Decimal

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.invoice import Invoice
from kolayis.models.payment import Payment
from kolayis.schemas.payment import PaymentCreate


def _get_invoice_for_owner(db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
    """Faturanin sahibi kontrolu ile fatura getir."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.owner_id == owner_id
    ).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fatura bulunamadi"
        )
    return invoice


def get_payments(db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> list[Payment]:
    """Bir faturanin tum odemelerini getir."""
    # Ownership check
    _get_invoice_for_owner(db, invoice_id, owner_id)
    return (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.payment_date.desc())
        .all()
    )


def create_payment(
    db: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID, data: PaymentCreate
) -> Payment:
    """Faturaya odeme ekle. Toplam odeme fatura toplamini gecemez."""
    invoice = _get_invoice_for_owner(db, invoice_id, owner_id)

    # Iptal edilmis faturaya odeme yapilamaz
    if invoice.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Iptal edilmis faturaya odeme yapilamaz"
        )

    # Odeme tutari kontrolu: toplam odemeler fatura toplamini gecemez
    current_paid = invoice.paid_amount
    if current_paid + data.amount > invoice.total:
        max_allowed = invoice.total - current_paid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Odeme tutari kalan borcu asamaz. Maksimum odeme: {max_allowed:.2f} TL"
        )

    payment = Payment(
        invoice_id=invoice_id,
        amount=data.amount,
        payment_date=data.payment_date,
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(payment)
    db.flush()

    # Tum odemeler yapildiysa fatura durumunu "paid" yap
    db.refresh(invoice)
    if invoice.paid_amount >= invoice.total:
        invoice.status = "paid"

    db.commit()
    db.refresh(payment)
    return payment


def delete_payment(
    db: Session, payment_id: uuid.UUID, invoice_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Odeme sil. Fatura durumunu geri guncelle."""
    invoice = _get_invoice_for_owner(db, invoice_id, owner_id)

    payment = db.query(Payment).filter(
        Payment.id == payment_id, Payment.invoice_id == invoice_id
    ).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Odeme bulunamadi"
        )

    db.delete(payment)
    db.flush()

    # Odeme silindikten sonra fatura artik tam odenmis degilse durumu guncelle
    db.refresh(invoice)
    if invoice.paid_amount < invoice.total and invoice.status == "paid":
        invoice.status = "sent"

    db.commit()
