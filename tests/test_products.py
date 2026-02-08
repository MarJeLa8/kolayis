"""
KolayIS CRM - Urun (Product) Testleri

Product router henuz main.py'ye eklenmemis durumda.
Bu nedenle testler dogrudan service katmanini test eder.
Router eklendiginde endpoint testleri de eklenebilir.

Test edilen fonksiyonlar (kolayis.services.product):
    create_product  - Urun olusturma
    get_products    - Urun listeleme
    get_product     - Urun detay
    update_product  - Urun guncelleme
    delete_product  - Urun silme
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from kolayis.services import product as product_service
from kolayis.schemas.product import ProductCreate, ProductUpdate


class TestCreateProduct:
    """Urun olusturma testleri."""

    def test_create_product(self, db_session, test_user):
        """Yeni urun basariyla olusturulabilmeli."""
        data = ProductCreate(
            name="Web Sitesi Tasarimi",
            description="Kurumsal web sitesi tasarimi hizmeti",
            unit_price=Decimal("5000.00"),
            unit="adet",
            tax_rate=20,
            stock=None,
        )
        product = product_service.create_product(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )
        assert product.name == "Web Sitesi Tasarimi"
        assert product.description == "Kurumsal web sitesi tasarimi hizmeti"
        assert product.unit_price == Decimal("5000.00")
        assert product.unit == "adet"
        assert product.tax_rate == 20
        assert product.stock is None
        assert product.owner_id == test_user.id
        assert product.id is not None

    def test_create_product_with_stock(self, db_session, test_user):
        """Stok bilgisi ile urun olusturulabilmeli."""
        data = ProductCreate(
            name="Ahsap Panel",
            unit_price=Decimal("250.00"),
            unit="metre",
            tax_rate=20,
            stock=500,
        )
        product = product_service.create_product(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )
        assert product.stock == 500
        assert product.unit == "metre"

    def test_create_product_minimal(self, db_session, test_user):
        """Sadece zorunlu alanlarla urun olusturulabilmeli."""
        data = ProductCreate(
            name="Basit Urun",
            unit_price=Decimal("10.00"),
        )
        product = product_service.create_product(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )
        assert product.name == "Basit Urun"
        assert product.unit == "adet"  # Varsayilan deger
        assert product.tax_rate == 20   # Varsayilan deger


class TestListProducts:
    """Urun listeleme testleri."""

    def test_list_products(self, db_session, test_user, test_product):
        """Urun listesi bos olmamali (test_product fixture'u var)."""
        products, total = product_service.get_products(
            db=db_session,
            owner_id=test_user.id,
        )
        assert total >= 1
        assert len(products) >= 1
        # Test urunu listede olmali
        product_names = [p.name for p in products]
        assert "Test Urun" in product_names

    def test_list_products_empty(self, db_session, test_user):
        """Hic urun yoksa bos liste donmeli."""
        products, total = product_service.get_products(
            db=db_session,
            owner_id=test_user.id,
        )
        assert total == 0
        assert products == []

    def test_list_products_search(self, db_session, test_user):
        """Arama parametresi calismali."""
        # Iki farkli urun olustur
        for name in ["Mutfak Dolabi", "Banyo Dolabi"]:
            data = ProductCreate(name=name, unit_price=Decimal("100.00"))
            product_service.create_product(db=db_session, owner_id=test_user.id, data=data)

        # "Mutfak" ile ara
        products, total = product_service.get_products(
            db=db_session,
            owner_id=test_user.id,
            search="Mutfak",
        )
        assert total == 1
        assert products[0].name == "Mutfak Dolabi"

    def test_list_products_pagination(self, db_session, test_user):
        """Sayfalama calismali."""
        # 5 urun olustur
        for i in range(5):
            data = ProductCreate(name=f"Urun {i}", unit_price=Decimal("100.00"))
            product_service.create_product(db=db_session, owner_id=test_user.id, data=data)

        # Sayfa 1, boyut 3
        products, total = product_service.get_products(
            db=db_session,
            owner_id=test_user.id,
            page=1,
            size=3,
        )
        assert total == 5
        assert len(products) == 3

    def test_list_products_isolation(self, db_session, test_user):
        """Bir kullanicinin urunleri baska kullaniciya gorunmemeli."""
        from kolayis.models.user import User
        from kolayis.services.auth import hash_password

        # Ikinci kullanici olustur
        other_user = User(
            id=uuid.uuid4(),
            email="other@kolayis.com",
            hashed_password=hash_password("Other1234!"),
            full_name="Diger Kullanici",
            is_active=True,
        )
        db_session.add(other_user)
        db_session.commit()

        # Her iki kullanici icin urun olustur
        data1 = ProductCreate(name="Kullanici1 Urun", unit_price=Decimal("100.00"))
        data2 = ProductCreate(name="Kullanici2 Urun", unit_price=Decimal("200.00"))
        product_service.create_product(db=db_session, owner_id=test_user.id, data=data1)
        product_service.create_product(db=db_session, owner_id=other_user.id, data=data2)

        # test_user sadece kendi urununu gormeli
        products, total = product_service.get_products(
            db=db_session, owner_id=test_user.id,
        )
        assert total == 1
        assert products[0].name == "Kullanici1 Urun"


class TestGetProduct:
    """Urun detay testleri."""

    def test_get_product(self, db_session, test_user, test_product):
        """Urun detayi basariyla getirilmeli."""
        product = product_service.get_product(
            db=db_session,
            product_id=test_product.id,
            owner_id=test_user.id,
        )
        assert product.id == test_product.id
        assert product.name == "Test Urun"
        assert product.unit_price == Decimal("150.00")

    def test_get_product_not_found(self, db_session, test_user):
        """Olmayan urun icin 404 hatasi firlatmali."""
        fake_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            product_service.get_product(
                db=db_session,
                product_id=fake_id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404


class TestUpdateProduct:
    """Urun guncelleme testleri."""

    def test_update_product(self, db_session, test_user, test_product):
        """Urun bilgileri basariyla guncellenebilmeli."""
        data = ProductUpdate(
            name="Guncellenmis Urun",
            unit_price=Decimal("200.00"),
        )
        product = product_service.update_product(
            db=db_session,
            product_id=test_product.id,
            owner_id=test_user.id,
            data=data,
        )
        assert product.name == "Guncellenmis Urun"
        assert product.unit_price == Decimal("200.00")
        # Gonderilmeyen alanlar degismemeli
        assert product.unit == "adet"
        assert product.tax_rate == 20


class TestDeleteProduct:
    """Urun silme testleri."""

    def test_delete_product(self, db_session, test_user, test_product):
        """Urun basariyla silinebilmeli."""
        product_service.delete_product(
            db=db_session,
            product_id=test_product.id,
            owner_id=test_user.id,
        )
        # Silindikten sonra erismeye calisinca 404 donmeli
        with pytest.raises(HTTPException) as exc_info:
            product_service.get_product(
                db=db_session,
                product_id=test_product.id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404

    def test_delete_nonexistent_product(self, db_session, test_user):
        """Olmayan urunu silmeye calismak 404 donmeli."""
        fake_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            product_service.delete_product(
                db=db_session,
                product_id=fake_id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404
