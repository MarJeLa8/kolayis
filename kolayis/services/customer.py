import uuid
from datetime import datetime

from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.customer import Customer
from kolayis.schemas.customer import CustomerCreate, CustomerUpdate
from kolayis.services.activity import log_activity


def get_customers(
    db: Session,
    owner_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    customer_status: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Customer], int]:
    """
    Kullanicinin musterilerini listele.
    Sayfalama, arama, durum filtreleme, tarih araligi ve siralama destekler.
    Dondurur: (musteri_listesi, toplam_sayi)
    """
    query = db.query(Customer).filter(Customer.owner_id == owner_id)

    # Arama: sirket adi, ilgili kisi adi veya email icinde ara
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Customer.company_name.ilike(search_filter),
                Customer.contact_name.ilike(search_filter),
                Customer.email.ilike(search_filter),
            )
        )

    # Durum filtresi
    if customer_status:
        query = query.filter(Customer.status == customer_status)

    # Tarih araligi filtresi
    if created_after:
        query = query.filter(Customer.created_at >= created_after)
    if created_before:
        query = query.filter(Customer.created_at <= created_before)

    # Toplam kayit sayisi (sayfalama icin)
    total = query.count()

    # Siralama: izin verilen alanlardan birine gore
    allowed_sort_fields = {
        "created_at": Customer.created_at,
        "company_name": Customer.company_name,
        "contact_name": Customer.contact_name,
        "status": Customer.status,
    }
    sort_column = allowed_sort_fields.get(sort_by, Customer.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Sayfalama: OFFSET ve LIMIT ile
    offset = (page - 1) * size
    customers = query.offset(offset).limit(size).all()

    return customers, total


def get_customer_stats(db: Session, owner_id: uuid.UUID) -> dict:
    """
    Musteri istatistiklerini dondur.
    Toplam musteri, duruma gore dagilim, bu ayin yeni musterileri.
    """
    base_query = db.query(Customer).filter(Customer.owner_id == owner_id)

    total = base_query.count()

    # Duruma gore dagilim
    status_counts = (
        base_query
        .with_entities(Customer.status, func.count(Customer.id))
        .group_by(Customer.status)
        .all()
    )
    by_status = {s: count for s, count in status_counts}

    # Bu ayin yeni musterileri
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = base_query.filter(Customer.created_at >= first_of_month).count()

    return {
        "total": total,
        "by_status": by_status,
        "new_this_month": new_this_month,
    }


def get_customer(
    db: Session, customer_id: uuid.UUID, owner_id: uuid.UUID
) -> Customer:
    """Tek bir musteriyi getir. Sahiplik kontrolu yapar."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.owner_id == owner_id,
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Musteri bulunamadi",
        )
    return customer


def create_customer(
    db: Session, owner_id: uuid.UUID, data: CustomerCreate
) -> Customer:
    """Yeni musteri olustur."""
    customer = Customer(
        owner_id=owner_id,
        **data.model_dump(),
    )
    db.add(customer)
    db.flush()
    log_activity(
        db, owner_id, "create", "customer", customer.id,
        f"Musteri '{data.company_name}' olusturuldu",
    )
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(
    db: Session, customer_id: uuid.UUID, owner_id: uuid.UUID, data: CustomerUpdate
) -> Customer:
    """
    Musteriyi guncelle.
    exclude_unset=True: sadece gonderilen alanlari gunceller,
    gonderilmeyenleri olduklari gibi birakir.
    """
    customer = get_customer(db, customer_id, owner_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    log_activity(
        db, owner_id, "update", "customer", customer_id,
        f"Musteri '{customer.company_name}' guncellendi",
    )
    db.commit()
    db.refresh(customer)
    return customer


def get_monthly_customer_growth(db: Session, owner_id: uuid.UUID, months: int = 6) -> list[dict]:
    """
    Son N ayin musteri artis verisi.
    Dondurur: [{"month": "2026-01", "count": 5}, ...]
    """
    from sqlalchemy import extract, text
    from datetime import datetime, timedelta

    # Son N ayin baslangic tarihini hesapla
    now = datetime.utcnow()
    start = now.replace(day=1) - timedelta(days=30 * (months - 1))
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(
            func.to_char(Customer.created_at, 'YYYY-MM').label('month'),
            func.count(Customer.id).label('count'),
        )
        .filter(Customer.owner_id == owner_id, Customer.created_at >= start)
        .group_by(func.to_char(Customer.created_at, 'YYYY-MM'))
        .order_by(func.to_char(Customer.created_at, 'YYYY-MM'))
        .all()
    )
    return [{"month": r.month, "count": r.count} for r in rows]


def delete_customer(
    db: Session, customer_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Musteriyi sil."""
    customer = get_customer(db, customer_id, owner_id)
    company_name = customer.company_name
    db.delete(customer)
    log_activity(
        db, owner_id, "delete", "customer", customer_id,
        f"Musteri '{company_name}' silindi",
    )
    db.commit()
