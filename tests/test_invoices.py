"""
KolayIS CRM - Fatura (Invoice) Testleri

Invoice router henuz main.py'ye eklenmemis durumda.
Bu nedenle testler dogrudan service katmanini test eder.

Test edilen fonksiyonlar (kolayis.services.invoice):
    create_invoice          - Fatura olusturma
    get_invoices            - Fatura listeleme
    get_invoice             - Fatura detay
    update_invoice_status   - Fatura durumu degistirme
    delete_invoice          - Fatura silme

Ek olarak KDV hesaplama dogrulugu test edilir.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from kolayis.services import invoice as invoice_service
from kolayis.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceUpdate


class TestCreateInvoice:
    """Fatura olusturma testleri."""

    def test_create_invoice(self, db_session, test_user, test_customer):
        """Fatura basariyla olusturulabilmeli."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            status="draft",
            notes="Test faturasi",
            items=[
                InvoiceItemCreate(
                    description="Web Sitesi Tasarimi",
                    quantity=Decimal("1"),
                    unit_price=Decimal("5000.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )
        assert invoice.customer_id == test_customer.id
        assert invoice.invoice_date == date(2026, 1, 15)
        assert invoice.due_date == date(2026, 2, 15)
        assert invoice.status == "draft"
        assert invoice.notes == "Test faturasi"
        assert invoice.invoice_number.startswith("FTR-")
        assert len(invoice.items) == 1
        assert invoice.id is not None

    def test_create_invoice_multiple_items(self, db_session, test_user, test_customer):
        """Birden fazla kalemli fatura olusturulabilmeli."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 2, 1),
            items=[
                InvoiceItemCreate(
                    description="Mutfak Dolabi",
                    quantity=Decimal("3"),
                    unit_price=Decimal("2000.00"),
                    tax_rate=20,
                ),
                InvoiceItemCreate(
                    description="Montaj Hizmeti",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )
        assert len(invoice.items) == 2

    def test_create_invoice_nonexistent_customer(self, db_session, test_user):
        """Olmayan musteri icin fatura olusturulamamamali."""
        fake_customer_id = uuid.uuid4()
        data = InvoiceCreate(
            customer_id=fake_customer_id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Test",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            invoice_service.create_invoice(
                db=db_session,
                owner_id=test_user.id,
                data=data,
            )
        assert exc_info.value.status_code == 404

    def test_create_invoice_auto_number(self, db_session, test_user, test_customer):
        """Fatura numarasi otomatik artmali (FTR-0001, FTR-0002, ...)."""
        # Birinci fatura
        data1 = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Urun 1",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice1 = invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data1,
        )
        assert invoice1.invoice_number == "FTR-0001"

        # Ikinci fatura
        data2 = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 2),
            items=[
                InvoiceItemCreate(
                    description="Urun 2",
                    quantity=Decimal("1"),
                    unit_price=Decimal("200.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice2 = invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data2,
        )
        assert invoice2.invoice_number == "FTR-0002"


class TestInvoiceCalculation:
    """KDV ve toplam hesaplama testleri."""

    def test_invoice_calculation_single_item(self, db_session, test_user, test_customer):
        """
        Tek kalemli faturada KDV hesaplamasi dogrulugu.

        Ornek:
            1 adet x 1000.00 TL = 1000.00 TL (ara toplam)
            KDV %20 = 200.00 TL
            Genel toplam = 1200.00 TL
        """
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Danismanlik Hizmeti",
                    quantity=Decimal("1"),
                    unit_price=Decimal("1000.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )

        # Ara toplam (subtotal): 1 x 1000 = 1000
        assert invoice.subtotal == Decimal("1000.00")
        # KDV toplami: 1000 * 0.20 = 200
        assert invoice.tax_total == Decimal("200.00")
        # Genel toplam: 1000 + 200 = 1200
        assert invoice.total == Decimal("1200.00")

        # Kalem bazinda kontrol
        item = invoice.items[0]
        assert item.line_total == Decimal("1000.00")
        assert item.tax_amount == Decimal("200.00")

    def test_invoice_calculation_multiple_items(self, db_session, test_user, test_customer):
        """
        Cok kalemli faturada KDV hesaplamasi dogrulugu.

        Kalem 1: 5 adet x 200.00 TL = 1000.00 TL, KDV %20 = 200.00 TL
        Kalem 2: 2 adet x 350.00 TL = 700.00 TL, KDV %10 = 70.00 TL

        Ara toplam: 1700.00 TL
        KDV toplami: 270.00 TL
        Genel toplam: 1970.00 TL
        """
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 2, 1),
            items=[
                InvoiceItemCreate(
                    description="Urun A",
                    quantity=Decimal("5"),
                    unit_price=Decimal("200.00"),
                    tax_rate=20,
                ),
                InvoiceItemCreate(
                    description="Urun B",
                    quantity=Decimal("2"),
                    unit_price=Decimal("350.00"),
                    tax_rate=10,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )

        # Kalem 1 kontrolu
        item_a = next(i for i in invoice.items if i.description == "Urun A")
        assert item_a.line_total == Decimal("1000.00")   # 5 x 200
        assert item_a.tax_amount == Decimal("200.00")    # 1000 * 0.20

        # Kalem 2 kontrolu
        item_b = next(i for i in invoice.items if i.description == "Urun B")
        assert item_b.line_total == Decimal("700.00")    # 2 x 350
        assert item_b.tax_amount == Decimal("70.00")     # 700 * 0.10

        # Fatura toplam kontrolleri
        assert invoice.subtotal == Decimal("1700.00")    # 1000 + 700
        assert invoice.tax_total == Decimal("270.00")    # 200 + 70
        assert invoice.total == Decimal("1970.00")       # 1700 + 270

    def test_invoice_calculation_zero_tax(self, db_session, test_user, test_customer):
        """
        KDV %0 olan kalem icin hesaplama dogrulugu.

        10 adet x 50.00 TL = 500.00 TL
        KDV %0 = 0.00 TL
        Toplam = 500.00 TL
        """
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 3, 1),
            items=[
                InvoiceItemCreate(
                    description="KDV'siz Urun",
                    quantity=Decimal("10"),
                    unit_price=Decimal("50.00"),
                    tax_rate=0,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )

        assert invoice.subtotal == Decimal("500.00")
        assert invoice.tax_total == Decimal("0.00")
        assert invoice.total == Decimal("500.00")

    def test_invoice_calculation_decimal_precision(self, db_session, test_user, test_customer):
        """
        Ondalik hesaplama hassasiyeti testi.

        3 adet x 33.33 TL = 99.99 TL
        KDV %18 = 17.9982 -> yuvarlanarak 18.00 TL
        Toplam = 99.99 + 18.00 = 117.99 TL
        """
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 3, 15),
            items=[
                InvoiceItemCreate(
                    description="Hassas Hesap Urunu",
                    quantity=Decimal("3"),
                    unit_price=Decimal("33.33"),
                    tax_rate=18,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session,
            owner_id=test_user.id,
            data=data,
        )

        item = invoice.items[0]
        assert item.line_total == Decimal("99.99")   # 3 x 33.33
        assert item.tax_amount == Decimal("18.00")   # 99.99 * 0.18 = 17.9982 -> 18.00
        assert invoice.subtotal == Decimal("99.99")
        assert invoice.tax_total == Decimal("18.00")
        assert invoice.total == Decimal("117.99")


class TestGetInvoice:
    """Fatura detay testleri."""

    def test_get_invoice(self, db_session, test_user, test_customer):
        """Fatura detayi basariyla getirilmeli."""
        # Once fatura olustur
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Test Urun",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        created = invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data,
        )

        # Fatura detayini getir
        invoice = invoice_service.get_invoice(
            db=db_session,
            invoice_id=created.id,
            owner_id=test_user.id,
        )
        assert invoice.id == created.id
        assert invoice.invoice_number == created.invoice_number

    def test_get_invoice_not_found(self, db_session, test_user):
        """Olmayan fatura icin 404 hatasi firlatmali."""
        fake_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            invoice_service.get_invoice(
                db=db_session,
                invoice_id=fake_id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404


class TestListInvoices:
    """Fatura listeleme testleri."""

    def test_list_invoices(self, db_session, test_user, test_customer):
        """Fatura listesi calismali."""
        # 2 fatura olustur
        for i in range(2):
            data = InvoiceCreate(
                customer_id=test_customer.id,
                invoice_date=date(2026, 1, i + 1),
                items=[
                    InvoiceItemCreate(
                        description=f"Urun {i}",
                        quantity=Decimal("1"),
                        unit_price=Decimal("100.00"),
                        tax_rate=20,
                    ),
                ],
            )
            invoice_service.create_invoice(
                db=db_session, owner_id=test_user.id, data=data,
            )

        invoices, total = invoice_service.get_invoices(
            db=db_session, owner_id=test_user.id,
        )
        assert total == 2
        assert len(invoices) == 2

    def test_list_invoices_filter_by_customer(self, db_session, test_user, test_customer):
        """Musteriye gore filtreleme calismali."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Test",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data,
        )

        invoices, total = invoice_service.get_invoices(
            db=db_session,
            owner_id=test_user.id,
            customer_id=test_customer.id,
        )
        assert total == 1

        # Baska bir musteri ID'si ile filtreleme
        invoices2, total2 = invoice_service.get_invoices(
            db=db_session,
            owner_id=test_user.id,
            customer_id=uuid.uuid4(),
        )
        assert total2 == 0

    def test_list_invoices_filter_by_status(self, db_session, test_user, test_customer):
        """Duruma gore filtreleme calismali."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            status="draft",
            items=[
                InvoiceItemCreate(
                    description="Test",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data,
        )

        # draft filtresinde bulunmali
        invoices, total = invoice_service.get_invoices(
            db=db_session,
            owner_id=test_user.id,
            invoice_status="draft",
        )
        assert total == 1

        # paid filtresinde bulunmamali
        invoices2, total2 = invoice_service.get_invoices(
            db=db_session,
            owner_id=test_user.id,
            invoice_status="paid",
        )
        assert total2 == 0


class TestInvoiceStatus:
    """Fatura durumu degistirme testleri."""

    def test_update_invoice_status(self, db_session, test_user, test_customer):
        """Fatura durumu basariyla degistirilebilmeli."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            status="draft",
            items=[
                InvoiceItemCreate(
                    description="Test",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data,
        )
        assert invoice.status == "draft"

        # Durumu "sent" olarak degistir
        updated = invoice_service.update_invoice_status(
            db=db_session,
            invoice_id=invoice.id,
            owner_id=test_user.id,
            new_status="sent",
        )
        assert updated.status == "sent"

        # Durumu "paid" olarak degistir
        paid = invoice_service.update_invoice_status(
            db=db_session,
            invoice_id=invoice.id,
            owner_id=test_user.id,
            new_status="paid",
        )
        assert paid.status == "paid"


class TestDeleteInvoice:
    """Fatura silme testleri."""

    def test_delete_invoice(self, db_session, test_user, test_customer):
        """Fatura basariyla silinebilmeli."""
        data = InvoiceCreate(
            customer_id=test_customer.id,
            invoice_date=date(2026, 1, 1),
            items=[
                InvoiceItemCreate(
                    description="Silinecek Urun",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    tax_rate=20,
                ),
            ],
        )
        invoice = invoice_service.create_invoice(
            db=db_session, owner_id=test_user.id, data=data,
        )

        invoice_service.delete_invoice(
            db=db_session,
            invoice_id=invoice.id,
            owner_id=test_user.id,
        )

        # Silindikten sonra erismeye calisinca 404 donmeli
        with pytest.raises(HTTPException) as exc_info:
            invoice_service.get_invoice(
                db=db_session,
                invoice_id=invoice.id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404

    def test_delete_nonexistent_invoice(self, db_session, test_user):
        """Olmayan faturayi silmeye calismak 404 donmeli."""
        fake_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            invoice_service.delete_invoice(
                db=db_session,
                invoice_id=fake_id,
                owner_id=test_user.id,
            )
        assert exc_info.value.status_code == 404
