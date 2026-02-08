"""Ornek veri ekleme scripti"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from kolayis.database import engine
from kolayis.models.user import User
from kolayis.models.customer import Customer
from kolayis.models.product import Product
from kolayis.models.invoice import Invoice, InvoiceItem
from kolayis.services.auth import hash_password
from sqlalchemy.orm import Session

with Session(engine) as db:
    # 1. Admin kullanici olustur
    admin = User(
        email="admin@kolayis.com",
        hashed_password=hash_password("admin12345"),
        full_name="Admin KolayIS",
        role="admin",
        is_verified=True,
    )
    db.add(admin)
    db.flush()
    print("Admin olusturuldu: admin@kolayis.com / admin12345")

    # 2. Mevcut kullaniciya ornek veri ekle
    user_id = uuid.UUID("44700c7f-f894-40e2-91e2-1a051d26ac3b")

    # 10 Musteri
    customers_data = [
        ("Yildiz Teknoloji A.S.", "Ahmet Yildiz", "ahmet@yildiztek.com", "0532 111 2233", "Istanbul, Kadikoy", "1234567890"),
        ("Deniz Insaat Ltd.", "Mehmet Deniz", "mehmet@denizinsaat.com", "0533 222 3344", "Ankara, Cankaya", "2345678901"),
        ("Ay Gida San. Tic.", "Fatma Ay", "fatma@aygida.com", "0534 333 4455", "Izmir, Bornova", "3456789012"),
        ("Kara Lojistik", "Ali Kara", "ali@karalojistik.com", "0535 444 5566", "Bursa, Nilufer", "4567890123"),
        ("Gunes Mobilya", "Ayse Gunes", "ayse@gunesmobilya.com", "0536 555 6677", "Antalya, Muratpasa", "5678901234"),
        ("Bulut Yazilim", "Can Bulut", "can@bulutyazilim.com", "0537 666 7788", "Istanbul, Besiktas", "6789012345"),
        ("Dere Otomasyon", "Elif Dere", "elif@dereoto.com", "0538 777 8899", "Kocaeli, Gebze", "7890123456"),
        ("Tas Mimarlik", "Burak Tas", "burak@tasmimarlik.com", "0539 888 9900", "Ankara, Etimesgut", "8901234567"),
        ("Celik Metal San.", "Zeynep Celik", "zeynep@celikmetal.com", "0540 999 0011", "Gaziantep, Sehitkamil", "9012345678"),
        ("Yesil Tarim", "Hasan Yesil", "hasan@yesiltar.com", "0541 000 1122", "Konya, Selcuklu", "0123456789"),
    ]

    customer_objs = []
    for name, contact, email, phone, addr, tax in customers_data:
        c = Customer(
            owner_id=user_id,
            company_name=name,
            contact_name=contact,
            email=email,
            phone=phone,
            address=addr,
            tax_number=tax,
            status="active",
        )
        db.add(c)
        customer_objs.append(c)
    db.flush()
    print(f"{len(customer_objs)} musteri eklendi")

    # 10 Urun
    products_data = [
        ("Web Sitesi Tasarimi", "Kurumsal web sitesi", Decimal("15000"), "adet", 20),
        ("SEO Hizmeti", "Aylik SEO optimizasyonu", Decimal("3000"), "adet", 20),
        ("Logo Tasarimi", "Kurumsal kimlik logosu", Decimal("5000"), "adet", 20),
        ("Mobil Uygulama", "iOS/Android uygulama", Decimal("50000"), "adet", 20),
        ("Hosting (Yillik)", "Sunucu barindirma", Decimal("2400"), "adet", 20),
        ("Teknik Destek", "Saatlik teknik destek", Decimal("500"), "saat", 20),
        ("E-ticaret Modulu", "Online satis sistemi", Decimal("25000"), "adet", 20),
        ("SSL Sertifikasi", "Yillik SSL", Decimal("800"), "adet", 20),
        ("Domain Kaydi", "Yillik domain", Decimal("300"), "adet", 20),
        ("Sosyal Medya Yonetimi", "Aylik icerik uretimi", Decimal("4000"), "adet", 20),
    ]

    product_objs = []
    for name, desc, price, unit, tax in products_data:
        p = Product(
            owner_id=user_id,
            name=name,
            description=desc,
            unit_price=price,
            unit=unit,
            tax_rate=tax,
            stock=10,
        )
        db.add(p)
        product_objs.append(p)
    db.flush()
    print(f"{len(product_objs)} urun eklendi")

    # 10 Fatura
    today = date.today()
    invoices_data = [
        (customer_objs[0], today - timedelta(days=5), today + timedelta(days=25), "sent", [
            ("Web Sitesi Tasarimi", 1, Decimal("15000"), 20),
            ("Hosting (Yillik)", 1, Decimal("2400"), 20),
        ]),
        (customer_objs[1], today - timedelta(days=15), today + timedelta(days=15), "sent", [
            ("Logo Tasarimi", 1, Decimal("5000"), 20),
        ]),
        (customer_objs[2], today - timedelta(days=30), today - timedelta(days=1), "sent", [
            ("SEO Hizmeti", 3, Decimal("3000"), 20),
        ]),
        (customer_objs[3], today - timedelta(days=10), today + timedelta(days=20), "paid", [
            ("Teknik Destek", 8, Decimal("500"), 20),
        ]),
        (customer_objs[4], today - timedelta(days=45), today - timedelta(days=15), "paid", [
            ("E-ticaret Modulu", 1, Decimal("25000"), 20),
            ("SSL Sertifikasi", 1, Decimal("800"), 20),
            ("Domain Kaydi", 1, Decimal("300"), 20),
        ]),
        (customer_objs[5], today - timedelta(days=3), today + timedelta(days=27), "draft", [
            ("Mobil Uygulama", 1, Decimal("50000"), 20),
        ]),
        (customer_objs[6], today - timedelta(days=20), today + timedelta(days=10), "sent", [
            ("Sosyal Medya Yonetimi", 6, Decimal("4000"), 20),
        ]),
        (customer_objs[7], today - timedelta(days=60), today - timedelta(days=30), "paid", [
            ("Web Sitesi Tasarimi", 1, Decimal("15000"), 20),
            ("Logo Tasarimi", 1, Decimal("5000"), 20),
        ]),
        (customer_objs[8], today - timedelta(days=7), today + timedelta(days=23), "sent", [
            ("Hosting (Yillik)", 5, Decimal("2400"), 20),
        ]),
        (customer_objs[9], today - timedelta(days=2), today + timedelta(days=28), "draft", [
            ("Teknik Destek", 4, Decimal("500"), 20),
            ("SEO Hizmeti", 1, Decimal("3000"), 20),
        ]),
    ]

    inv_count = 0
    for cust, inv_date, due_date, status, items in invoices_data:
        inv_count += 1
        inv_number = f"FTR-2026-{inv_count:04d}"

        subtotal = sum(qty * price for _, qty, price, _ in items)
        tax_total = sum(qty * price * tax / 100 for _, qty, price, tax in items)

        inv = Invoice(
            owner_id=user_id,
            customer_id=cust.id,
            invoice_number=inv_number,
            invoice_date=inv_date,
            due_date=due_date,
            status=status,
            subtotal=subtotal,
            tax_total=tax_total,
            total=subtotal + tax_total,
        )
        db.add(inv)
        db.flush()

        for desc, qty, price, tax in items:
            line = qty * price
            tax_amt = line * tax / 100
            item = InvoiceItem(
                invoice_id=inv.id,
                description=desc,
                quantity=qty,
                unit_price=price,
                tax_rate=tax,
                line_total=line,
                tax_amount=tax_amt,
            )
            db.add(item)

    db.commit()
    print(f"{inv_count} fatura eklendi")
    print("Tum ornek veriler basariyla eklendi!")
