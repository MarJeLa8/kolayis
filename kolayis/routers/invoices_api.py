"""
Fatura REST API Router'i.

Fatura CRUD islemlerini, odeme yonetimini ve e-fatura XML indirmeyi
REST API uzerinden saglar.
Tum endpoint'ler JWT authentication gerektirir.
Her kullanici sadece kendi faturalarini gorebilir/duzenleyebilir (owner_id kontrolu).

Endpoint'ler:
    GET    /                   -> Fatura listesi (sayfalama + arama + status filtre)
    GET    /{invoice_id}       -> Fatura detay (kalemler + odemeler dahil)
    POST   /                   -> Yeni fatura olustur
    PUT    /{invoice_id}       -> Fatura guncelle (musteri, tarih, not)
    DELETE /{invoice_id}       -> Fatura sil
    POST   /{invoice_id}/payments  -> Odeme ekle
    GET    /{invoice_id}/xml   -> E-fatura XML indir

Bu router main.py'de su sekilde eklenir:
    app.include_router(invoices_api.router, prefix="/api/v1/invoices", tags=["Invoices"])
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from kolayis.dependencies import get_db, get_current_user
from kolayis.models.user import User
from kolayis.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceItemResponse,
)
from kolayis.schemas.payment import PaymentCreate, PaymentResponse
from kolayis.services import invoice as invoice_service
from kolayis.services import payment as payment_service
from kolayis.services.einvoice import generate_ubl_xml

router = APIRouter()


# ============================================================
# Response modelleri
# ============================================================

from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from decimal import Decimal


class InvoiceListItem(BaseModel):
    """
    Fatura listesi icin kisaltilmis response modeli.
    Kalemler ve odemeler dahil edilmez (performans icin).
    """
    id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    status: str
    notes: str | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    """Fatura listesi (sayfalama destekli)."""
    items: list[InvoiceListItem]
    total: int
    page: int
    size: int


class InvoiceDetailResponse(BaseModel):
    """
    Fatura detay response modeli.
    Kalemler ve odemeler dahil.
    """
    id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    status: str
    notes: str | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    items: list[InvoiceItemResponse] = []
    payments: list[PaymentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceStatusUpdate(BaseModel):
    """Fatura durum guncelleme."""
    status: str


# ============================================================
# Endpoint'ler
# ============================================================


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1, description="Sayfa numarasi"),
    size: int = Query(default=20, ge=1, le=100, description="Sayfa basi kayit sayisi"),
    search: str | None = Query(default=None, description="Fatura numarasina gore arama"),
    invoice_status: str | None = Query(
        default=None,
        alias="status",
        description="Durum filtresi (draft/sent/paid/cancelled)",
    ),
    customer_id: uuid.UUID | None = Query(default=None, description="Musteriye gore filtrele"),
    sort: str | None = Query(default=None, description="Siralama (due_date_asc, due_date_desc)"),
):
    """
    Kullanicinin fatura listesini dondurur.

    - Sayfalama: page ve size parametreleri ile
    - Arama: search parametresi ile fatura numarasinda arama
    - Filtre: status parametresi ile durum filtreleme (draft, sent, paid, cancelled)
    - Filtre: customer_id parametresi ile musteriye gore filtreleme
    - Siralama: sort parametresi ile (due_date_asc, due_date_desc; varsayilan: created_at desc)

    Ornek:
        GET /api/v1/invoices?page=1&size=10&status=draft&sort=due_date_asc
    """
    invoices, total = invoice_service.get_invoices(
        db=db,
        owner_id=current_user.id,
        customer_id=customer_id,
        invoice_status=invoice_status,
        page=page,
        size=size,
        sort=sort,
    )
    return InvoiceListResponse(
        items=invoices,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Belirli bir faturanin detayini dondurur.

    Kalemler (items) ve odemeler (payments) dahil edilir.
    paid_amount ve remaining_amount hesaplanmis olarak doner.

    - invoice_id: Faturanin UUID'si
    - Fatura bulunamazsa 404 doner
    """
    invoice = invoice_service.get_invoice(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
    )
    return InvoiceDetailResponse(
        id=invoice.id,
        customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        status=invoice.status,
        notes=invoice.notes,
        subtotal=invoice.subtotal,
        tax_total=invoice.tax_total,
        total=invoice.total,
        paid_amount=invoice.paid_amount,
        remaining_amount=invoice.remaining_amount,
        items=invoice.items,
        payments=invoice.payments,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: InvoiceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Yeni fatura olusturur.

    Request body (InvoiceCreate):
    - customer_id: Musterinin UUID'si (zorunlu)
    - invoice_date: Fatura tarihi (zorunlu, YYYY-MM-DD)
    - due_date: Vade tarihi (opsiyonel, YYYY-MM-DD)
    - status: Durum (varsayilan: "draft")
    - notes: Aciklama/not (opsiyonel)
    - items: Fatura kalemleri listesi
        - description: Kalem aciklamasi (zorunlu)
        - quantity: Miktar (zorunlu, >= 0)
        - unit_price: Birim fiyat (zorunlu, >= 0)
        - tax_rate: KDV orani % (varsayilan: 20)
        - product_id: Iliskili urun UUID'si (opsiyonel)

    Fatura numarasi otomatik olusturulur (FTR-0001, FTR-0002, ...).
    Kalem toplamlari ve KDV otomatik hesaplanir.
    Aktivite loguna kaydedilir.
    """
    return invoice_service.create_invoice(
        db=db,
        owner_id=current_user.id,
        data=data,
    )


@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Mevcut bir faturayi gunceller.

    Sadece taslak (draft) ve gonderilmis (sent) faturalar guncellenebilir.
    Odenmis veya iptal edilmis faturalar guncellenemez.

    Guncellenebilir alanlar:
    - customer_id: Musteri
    - invoice_date: Fatura tarihi
    - due_date: Vade tarihi
    - notes: Notlar

    Fatura bulunamazsa 404, durum uygun degilse 400 doner.
    """
    return invoice_service.update_invoice(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
        data=data,
    )


@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: uuid.UUID,
    data: InvoiceStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Fatura durumunu gunceller.

    Gecerli durumlar: draft, sent, paid, cancelled

    Ornek: {"status": "sent"}

    Aktivite loguna kaydedilir.
    """
    valid_statuses = ("draft", "sent", "paid", "cancelled")
    if data.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gecersiz durum. Gecerli durumlar: {', '.join(valid_statuses)}",
        )
    return invoice_service.update_invoice_status(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
        new_status=data.status,
    )


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Faturayi siler.

    - Fatura ile birlikte tum kalemleri ve odemeleri de silinir
      (cascade delete sayesinde)
    - Aktivite loguna kaydedilir
    - Basarili olursa 204 No Content doner (body yok)
    """
    invoice_service.delete_invoice(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
    )


# ============================================================
# Odeme Endpoint'leri
# ============================================================


@router.get("/{invoice_id}/payments", response_model=list[PaymentResponse])
def list_payments(
    invoice_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Faturanin odemelerini listeler.

    Odemeler tarih sirasina gore (en yeniden en eskiye) siralanir.
    """
    return payment_service.get_payments(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
    )


@router.post(
    "/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    invoice_id: uuid.UUID,
    data: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Faturaya odeme ekler.

    Request body (PaymentCreate):
    - amount: Odeme tutari (zorunlu, > 0)
    - payment_date: Odeme tarihi (zorunlu, YYYY-MM-DD)
    - payment_method: Odeme yontemi (varsayilan: "bank_transfer")
      Secenekler: bank_transfer, cash, credit_card, check
    - notes: Not (opsiyonel)

    Kontroller:
    - Iptal edilmis faturaya odeme yapilamaz (400)
    - Toplam odeme fatura toplamini gecemez (400)
    - Tum borc odendiginde fatura durumu otomatik "paid" olur

    Basarili olursa 201 Created ile odeme bilgisini dondurur.
    """
    return payment_service.create_payment(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
        data=data,
    )


# ============================================================
# E-Fatura XML Endpoint'i
# ============================================================


@router.get("/{invoice_id}/xml")
def get_invoice_xml(
    invoice_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Faturanin UBL-TR 2.1 formatinda e-fatura XML'ini dondurur.

    Response:
    - Content-Type: application/xml
    - Content-Disposition: attachment (otomatik indirme)
    - Dosya adi: {fatura_numarasi}.xml (orn: FTR-0001.xml)

    XML icerigi GIB e-fatura standartlarina uygun UBL-TR 2.1 formatindadir.
    Icerik: fatura bilgileri, satici/alici, kalemler, KDV hesaplari, toplamlar.
    """
    invoice = invoice_service.get_invoice(
        db=db,
        invoice_id=invoice_id,
        owner_id=current_user.id,
    )

    # XML olustur
    xml_content = generate_ubl_xml(
        invoice=invoice,
        customer=invoice.customer,
        items=invoice.items,
        user=current_user,
    )

    # XML dosyasi olarak dondur
    filename = f"{invoice.invoice_number}.xml"
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
