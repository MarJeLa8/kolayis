import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.product import Product
from kolayis.schemas.product import ProductCreate, ProductUpdate
from kolayis.services.activity import log_activity


def get_products(
    db: Session, owner_id: uuid.UUID, search: str | None = None,
    page: int = 1, size: int = 20,
) -> tuple[list[Product], int]:
    """
    Urun listesini sayfalama ile dondur.
    Dondurur: (urun_listesi, toplam_sayi)
    """
    query = db.query(Product).filter(Product.owner_id == owner_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    # Toplam kayit sayisi (sayfalama icin)
    total = query.count()

    # Sayfalama: OFFSET ve LIMIT ile
    offset = (page - 1) * size
    products = query.order_by(Product.name.asc()).offset(offset).limit(size).all()

    return products, total


def get_product(db: Session, product_id: uuid.UUID, owner_id: uuid.UUID) -> Product:
    product = db.query(Product).filter(
        Product.id == product_id, Product.owner_id == owner_id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Urun bulunamadi")
    return product


def create_product(db: Session, owner_id: uuid.UUID, data: ProductCreate) -> Product:
    product = Product(owner_id=owner_id, **data.model_dump())
    db.add(product)
    db.flush()
    log_activity(
        db, owner_id, "create", "product", product.id,
        f"Urun '{data.name}' olusturuldu",
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session, product_id: uuid.UUID, owner_id: uuid.UUID, data: ProductUpdate
) -> Product:
    product = get_product(db, product_id, owner_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    log_activity(
        db, owner_id, "update", "product", product_id,
        f"Urun '{product.name}' guncellendi",
    )
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    product = get_product(db, product_id, owner_id)
    product_name = product.name
    db.delete(product)
    log_activity(
        db, owner_id, "delete", "product", product_id,
        f"Urun '{product_name}' silindi",
    )
    db.commit()
