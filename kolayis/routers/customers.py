import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.dependencies import get_current_user
from kolayis.models.user import User
from kolayis.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)
from kolayis.services import customer as customer_service

router = APIRouter()


@router.get("/stats")
def customer_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Musteri istatistikleri.
    Toplam musteri sayisi, duruma gore dagilim, bu ayin yeni musterileri.
    """
    return customer_service.get_customer_stats(db=db, owner_id=current_user.id)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1, description="Sayfa numarasi"),
    size: int = Query(default=20, ge=1, le=100, description="Sayfa basi kayit"),
    search: str | None = Query(default=None, description="Arama (sirket, kisi, email)"),
    status: str | None = Query(default=None, description="Durum filtresi (active/inactive/lead)"),
    created_after: datetime | None = Query(default=None, description="Bu tarihten sonra olusturulanlar"),
    created_before: datetime | None = Query(default=None, description="Bu tarihten once olusturulanlar"),
    sort_by: str = Query(default="created_at", description="Siralama alani (created_at/company_name/contact_name/status)"),
    sort_order: str = Query(default="desc", description="Siralama yonu (asc/desc)"),
):
    """
    Musteri listesi.
    Sayfalama, arama, durum filtreleme, tarih araligi ve siralama destekler.
    """
    customers, total = customer_service.get_customers(
        db=db,
        owner_id=current_user.id,
        page=page,
        size=size,
        search=search,
        customer_status=status,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return CustomerListResponse(
        items=customers,
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Yeni musteri olustur."""
    return customer_service.create_customer(
        db=db,
        owner_id=current_user.id,
        data=data,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Musteri detayini getir."""
    return customer_service.get_customer(
        db=db,
        customer_id=customer_id,
        owner_id=current_user.id,
    )


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Musteriyi guncelle. Sadece gonderilen alanlar degisir."""
    return customer_service.update_customer(
        db=db,
        customer_id=customer_id,
        owner_id=current_user.id,
        data=data,
    )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Musteriyi sil."""
    customer_service.delete_customer(
        db=db,
        customer_id=customer_id,
        owner_id=current_user.id,
    )
