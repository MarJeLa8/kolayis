import uuid
import logging

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from kolayis.models.product import Product
from kolayis.models.stock_movement import StockMovement
from kolayis.services.activity import log_activity

logger = logging.getLogger(__name__)


def get_stock_movements(
    db: Session,
    owner_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[StockMovement]:
    """
    Stok hareketlerini listele.
    Opsiyonel olarak belirli bir urune filtrelenebilir.
    En yeniden en eskiye siralanir.
    """
    query = db.query(StockMovement).filter(StockMovement.owner_id == owner_id)

    if product_id:
        query = query.filter(StockMovement.product_id == product_id)

    return (
        query.order_by(StockMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def add_stock_movement(
    db: Session,
    owner_id: uuid.UUID,
    product_id: uuid.UUID,
    movement_type: str,
    quantity: int,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> StockMovement:
    """
    Stok hareketi ekle ve urun stogunu guncelle.

    movement_type'a gore stok hesaplama:
    - "in": stoga eklenir (+)
    - "out": stoktan dusulur (-)
    - "adjustment": stok miktari direkt olarak quantity'ye set edilir

    Onceki ve yeni stok degerleri StockMovement kaydinda saklanir (audit trail).
    """
    # Urunu bul
    product = db.query(Product).filter(
        Product.id == product_id, Product.owner_id == owner_id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Urun bulunamadi"
        )

    # Onceki stok degeri (null ise 0 olarak kabul et)
    previous_stock = product.stock if product.stock is not None else 0

    # Yeni stok degerini hesapla
    if movement_type == "in":
        new_stock = previous_stock + quantity
    elif movement_type == "out":
        new_stock = previous_stock - quantity
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yetersiz stok. Mevcut: {previous_stock}, Cikarilmak istenen: {quantity}"
            )
    elif movement_type == "adjustment":
        # Duzeltme: quantity dogrudan yeni stok degeri olur
        new_stock = quantity
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gecersiz hareket tipi. Gecerli tipler: in, out, adjustment"
        )

    # Urun stogunu guncelle
    product.stock = new_stock

    # Stok hareketi kaydini olustur
    movement = StockMovement(
        owner_id=owner_id,
        product_id=product_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type or "manual",
        reference_id=reference_id,
        notes=notes,
        previous_stock=previous_stock,
        new_stock=new_stock,
    )
    db.add(movement)
    db.flush()

    # Aktivite logu
    type_labels = {"in": "Giris", "out": "Cikis", "adjustment": "Duzeltme"}
    type_label = type_labels.get(movement_type, movement_type)
    log_activity(
        db, owner_id, "create", "stock_movement", movement.id,
        f"Stok hareketi: {product.name} - {type_label} ({quantity} adet, {previous_stock} -> {new_stock})",
    )

    db.commit()
    db.refresh(movement)
    return movement


def get_low_stock_products(
    db: Session,
    owner_id: uuid.UUID,
    threshold: int = 5,
) -> list[Product]:
    """
    Stoku belirtilen esik degerinin altinda olan urunleri getir.
    Stoku null olan urunler (hizmetler) dahil edilmez.
    Stok miktarina gore artan sirada siralanir.
    """
    return (
        db.query(Product)
        .filter(
            Product.owner_id == owner_id,
            Product.stock.isnot(None),
            Product.stock <= threshold,
        )
        .order_by(Product.stock.asc())
        .all()
    )


def get_stock_summary(
    db: Session,
    owner_id: uuid.UUID,
) -> dict:
    """
    Stok ozet bilgilerini dondur:
    - total_products: Toplam urun sayisi (stok takibi olan)
    - in_stock: Stokta olan urun sayisi (stock > 0)
    - low_stock: Dusuk stoklu urun sayisi (0 < stock <= 5)
    - out_of_stock: Stoksuz urun sayisi (stock == 0)
    """
    # Sadece stok takibi olan urunler (stock != null)
    base_query = db.query(Product).filter(
        Product.owner_id == owner_id,
        Product.stock.isnot(None),
    )

    total_products = base_query.count()
    in_stock = base_query.filter(Product.stock > 0).count()
    low_stock = base_query.filter(Product.stock > 0, Product.stock <= 5).count()
    out_of_stock = base_query.filter(Product.stock == 0).count()

    return {
        "total_products": total_products,
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
    }
