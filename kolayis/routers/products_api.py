"""
Urun REST API Router'i.

Urun CRUD islemlerini REST API uzerinden saglar.
Tum endpoint'ler JWT authentication gerektirir.
Her kullanici sadece kendi urunlerini gorebilir/duzenleyebilir (owner_id kontrolu).

Endpoint'ler:
    GET    /              -> Urun listesi (sayfalama + arama)
    GET    /{product_id}  -> Urun detay
    POST   /              -> Yeni urun olustur
    PUT    /{product_id}  -> Urun guncelle
    DELETE /{product_id}  -> Urun sil

Bu router main.py'de su sekilde eklenir:
    app.include_router(products_api.router, prefix="/api/v1/products", tags=["Products"])
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from kolayis.dependencies import get_db, get_current_user
from kolayis.models.user import User
from kolayis.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from kolayis.services import product as product_service

router = APIRouter()


# ============================================================
# Response modelleri (sayfalama destekli liste icin)
# ============================================================

from pydantic import BaseModel


class ProductListResponse(BaseModel):
    """
    Urun listesi response modeli.
    Sayfalama bilgisi ile birlikte urunleri dondurur.
    """
    items: list[ProductResponse]
    total: int
    page: int
    size: int


# ============================================================
# Endpoint'ler
# ============================================================


@router.get("", response_model=ProductListResponse)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1, description="Sayfa numarasi"),
    size: int = Query(default=20, ge=1, le=100, description="Sayfa basi kayit sayisi"),
    search: str | None = Query(default=None, description="Urun adina gore arama"),
):
    """
    Kullanicinin urun listesini dondurur.

    - Sayfalama: page ve size parametreleri ile
    - Arama: search parametresi ile urun adinda arama (ilike)
    - Siralama: urun adina gore A-Z (varsayilan)

    Ornek:
        GET /api/v1/products?page=1&size=10&search=dolap
    """
    products, total = product_service.get_products(
        db=db,
        owner_id=current_user.id,
        search=search,
        page=page,
        size=size,
    )
    return ProductListResponse(
        items=products,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Belirli bir urunun detayini dondurur.

    - product_id: Urunun UUID'si
    - Sadece kullanicinin kendi urunu gorulebilir (owner_id kontrolu)
    - Urun bulunamazsa 404 doner
    """
    return product_service.get_product(
        db=db,
        product_id=product_id,
        owner_id=current_user.id,
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Yeni urun olusturur.

    Request body (ProductCreate):
    - name: Urun adi (zorunlu, 1-255 karakter)
    - description: Urun aciklamasi (opsiyonel)
    - unit_price: Birim fiyat (zorunlu, >= 0)
    - unit: Birim (varsayilan: "adet")
    - tax_rate: KDV orani % (varsayilan: 20, 0-100 arasi)
    - stock: Stok adedi (opsiyonel)

    Basarili olursa 201 Created ile olusturulan urunu dondurur.
    Aktivite loguna kaydedilir.
    """
    return product_service.create_product(
        db=db,
        owner_id=current_user.id,
        data=data,
    )


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Mevcut bir urunu gunceller (partial update).

    Sadece gonderilen alanlar guncellenir, gonderilmeyen alanlar degismez.
    Ornegin sadece fiyat guncellemek icin: {"unit_price": 150.00}

    - product_id: Guncellenecek urunun UUID'si
    - Urun bulunamazsa 404 doner
    - Aktivite loguna kaydedilir
    """
    return product_service.update_product(
        db=db,
        product_id=product_id,
        owner_id=current_user.id,
        data=data,
    )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Urunu siler.

    - product_id: Silinecek urunun UUID'si
    - Urun bulunamazsa 404 doner
    - Urun fatura kalemlerinde kullaniliyorsa, o kalemlerde product_id NULL olur
      (ForeignKey ondelete="SET NULL" sayesinde)
    - Aktivite loguna kaydedilir
    - Basarili olursa 204 No Content doner (body yok)
    """
    product_service.delete_product(
        db=db,
        product_id=product_id,
        owner_id=current_user.id,
    )
