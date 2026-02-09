"""
Web arayuzu router'i.
API endpoint'leri JSON dondururken, bu router HTML sayfalari dondurur.
Cookie'de saklanan JWT token ile kimlik dogrulama yapar.
"""

import uuid
from typing import Annotated

import httpx

from fastapi import APIRouter, Depends, Form, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.models.user import User
from kolayis.services.auth import hash_password, verify_password, create_access_token, verify_token
from kolayis.services import customer as customer_service
from kolayis.services import note as note_service
from kolayis.services import product as product_service
from kolayis.services import invoice as invoice_service
from kolayis.services import payment as payment_service
from kolayis.schemas.customer import CustomerCreate, CustomerUpdate
from kolayis.schemas.note import NoteCreate
from kolayis.schemas.product import ProductCreate, ProductUpdate
from kolayis.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceUpdate
from kolayis.schemas.payment import PaymentCreate
from kolayis.services import email as email_service
from kolayis.services import activity as activity_service
from kolayis.services import quotation as quotation_service
from kolayis.services import expense as expense_service
from kolayis.services import recurring as recurring_service
from kolayis.services import attachment as attachment_service
from kolayis.services import stock as stock_service
from kolayis.services import webhook as webhook_service
from kolayis.services import bulk as bulk_service
from kolayis.services import calendar_service
from kolayis.services import einvoice as einvoice_service
from kolayis.services import import_service
from kolayis.services import roles as roles_service
from kolayis.services import notification as notification_service
from kolayis.services import deal as deal_service
from kolayis.services import ai_assistant
from kolayis.services import whatsapp as whatsapp_service
from kolayis.services import custom_field as custom_field_service
from kolayis.services import totp as totp_service
from kolayis.schemas.quotation import QuotationCreate, QuotationUpdate
from kolayis.schemas.expense import ExpenseCreate, ExpenseCategoryCreate, ExpenseUpdate
from kolayis.schemas.recurring import RecurringCreate, RecurringUpdate
from kolayis.schemas.webhook import WebhookCreate, WebhookUpdate
from kolayis.schemas.stock_movement import StockMovementCreate
from kolayis.models.quotation import Quotation
from kolayis.models.expense import Expense, ExpenseCategory
from kolayis.models.recurring import RecurringInvoice
from kolayis.models.webhook import Webhook
from kolayis.models.stock_movement import StockMovement

router = APIRouter()
templates = Jinja2Templates(directory="kolayis/templates")


# --- Yardimci fonksiyonlar ---

def get_current_user_from_cookie(request: Request, db: Session) -> User | None:
    """
    Cookie'deki JWT token'dan kullaniciyi dondur.
    Token yoksa veya gecersizse None dondurur (sayfa yonlendirme yapar).
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        user_id = verify_token(token)
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_active:
            return user
        return None
    except Exception:
        return None


def require_login(request: Request, db: Session) -> User | RedirectResponse:
    """Giris yapmamis kullaniciyi login sayfasina yonlendir."""
    user = get_current_user_from_cookie(request, db)
    if not user:
        return None
    return user


# Cloudflare Turnstile dogrulama
from kolayis.config import settings as app_settings
TURNSTILE_SITE_KEY = app_settings.TURNSTILE_SITE_KEY
TURNSTILE_SECRET_KEY = app_settings.TURNSTILE_SECRET_KEY

def verify_turnstile(token: str) -> bool:
    """Cloudflare Turnstile token'ini dogrula."""
    if not TURNSTILE_SECRET_KEY or not TURNSTILE_SITE_KEY:
        return True  # Key yoksa dogrulamayi atla (gelistirme ortami)
    if not token:
        return True  # Token bossa da atla (widget yuklenemedi)
    try:
        resp = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": token},
            timeout=10,
        )
        return resp.json().get("success", False)
    except Exception:
        return True  # Hata durumunda kullaniciyi engelleme


# --- Auth sayfalari ---

@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request, verified: str = ""):
    """Giris sayfasi"""
    ctx = {"request": request, "turnstile_site_key": TURNSTILE_SITE_KEY}
    if verified:
        ctx["success"] = "Email adresiniz dogrulandi. Simdi giris yapabilirsiniz."
    return templates.TemplateResponse("auth/login.html", ctx)


@router.post("/auth/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    """Giris formu gonderildiginde"""
    # Turnstile dogrulama
    form_data = await request.form()
    turnstile_token = form_data.get("cf-turnstile-response", "")
    if not verify_turnstile(turnstile_token):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "turnstile_site_key": TURNSTILE_SITE_KEY,
            "error": "Robot dogrulamasi basarisiz. Lutfen tekrar deneyin.",
        })

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "turnstile_site_key": TURNSTILE_SITE_KEY,
            "error": "Email veya sifre hatali",
        })

    # Email dogrulanmis mi kontrol et
    if not user.is_verified:
        return RedirectResponse(url=f"/auth/verify?email={email}", status_code=303)

    # JWT token olustur ve cookie'ye kaydet
    token = create_access_token(user.id)

    # Ilk giris mi? (hic musteri yoksa onboarding'e yonlendir)
    _, cust_count = customer_service.get_customers(db, user.id, size=1)
    redirect_url = "/onboarding" if cust_count == 0 else "/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response


@router.get("/auth/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Kayit sayfasi"""
    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "turnstile_site_key": TURNSTILE_SITE_KEY,
    })


@router.post("/auth/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Kayit formu gonderildiginde"""
    from kolayis.services.email import generate_verification_code, send_verification_email, is_email_configured

    # Turnstile dogrulama
    form_data = await request.form()
    turnstile_token = form_data.get("cf-turnstile-response", "")
    if not verify_turnstile(turnstile_token):
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "turnstile_site_key": TURNSTILE_SITE_KEY,
            "error": "Robot dogrulamasi basarisiz. Lutfen tekrar deneyin.",
        })

    # Email kontrolu
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "turnstile_site_key": TURNSTILE_SITE_KEY,
            "error": "Bu email adresi zaten kayitli",
        })

    if len(password) < 8:
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "turnstile_site_key": TURNSTILE_SITE_KEY,
            "error": "Sifre en az 8 karakter olmali",
        })

    # Dogrulama kodu olustur
    code = generate_verification_code()
    from datetime import datetime, timedelta, timezone
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)

    # Kullanici olustur (is_verified=False, role=user)
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_verified=False,
        verification_code=code,
        verification_code_expires=expires,
    )
    db.add(user)
    db.commit()

    # Dogrulama kodunu emaile gonder
    send_verification_email(email, full_name, code)

    # Dogrulama sayfasina yonlendir
    return RedirectResponse(url=f"/auth/verify?email={email}", status_code=303)


@router.get("/auth/verify", response_class=HTMLResponse)
def verify_page(request: Request, email: str = ""):
    """Email dogrulama sayfasi"""
    return templates.TemplateResponse("auth/verify.html", {
        "request": request,
        "email": email,
    })


@router.post("/auth/verify", response_class=HTMLResponse)
def verify_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    code: str = Form(...),
):
    """Dogrulama kodu kontrolu"""
    from datetime import datetime, timezone

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request, "email": email,
            "error": "Kullanici bulunamadi",
        })

    if user.is_verified:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Kod suresi dolmus mu?
    if user.verification_code_expires and user.verification_code_expires < datetime.now(timezone.utc):
        return templates.TemplateResponse("auth/verify.html", {
            "request": request, "email": email,
            "error": "Dogrulama kodunun suresi dolmus. Yeni kod isteyin.",
        })

    # Kod dogru mu?
    if user.verification_code != code:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request, "email": email,
            "error": "Dogrulama kodu hatali",
        })

    # Dogrulama basarili
    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    db.commit()

    return RedirectResponse(url="/auth/login?verified=1", status_code=303)


@router.post("/auth/resend-code", response_class=HTMLResponse)
def resend_code(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
):
    """Dogrulama kodunu tekrar gonder"""
    from kolayis.services.email import generate_verification_code, send_verification_email
    from datetime import datetime, timedelta, timezone

    user = db.query(User).filter(User.email == email).first()
    if user and not user.is_verified:
        code = generate_verification_code()
        user.verification_code = code
        user.verification_code_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.commit()
        send_verification_email(email, user.full_name, code)

    return templates.TemplateResponse("auth/verify.html", {
        "request": request, "email": email,
        "success": "Yeni dogrulama kodu gonderildi",
    })


@router.get("/auth/logout")
def logout():
    """Cikis yap - cookie'yi sil"""
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response


# --- Dashboard ---

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Ana sayfa - dashboard"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    stats = customer_service.get_customer_stats(db, user.id)
    invoice_stats = invoice_service.get_invoice_stats(db, user.id)
    recent_customers, _ = customer_service.get_customers(db, user.id, page=1, size=5)
    monthly_revenue = invoice_service.get_monthly_revenue(db, user.id)
    monthly_customers = customer_service.get_monthly_customer_growth(db, user.id)
    recent_invoices, _ = invoice_service.get_invoices(db, user.id, page=1, size=5)

    # Vadesi gecen ve yaklasan fatura istatistikleri (tum sent/draft faturalar)
    from datetime import date as date_cls
    all_invoices, _ = invoice_service.get_invoices(db, user.id, size=10000)
    today = date_cls.today()
    overdue_invoices = [
        inv for inv in all_invoices
        if inv.due_date and inv.status in ("sent", "draft") and inv.due_date < today
    ]
    upcoming_invoices = [
        inv for inv in all_invoices
        if inv.due_date and inv.status in ("sent", "draft")
        and 0 <= (inv.due_date - today).days <= 7
    ]

    recent_activities = activity_service.get_recent_activities(db, user.id, limit=10)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_page": "dashboard",
        "stats": stats,
        "invoice_stats": invoice_stats,
        "recent_customers": recent_customers,
        "monthly_revenue": monthly_revenue,
        "monthly_customers": monthly_customers,
        "recent_invoices": recent_invoices,
        "overdue_count": len(overdue_invoices),
        "overdue_total": float(sum(inv.total for inv in overdue_invoices)),
        "upcoming_count": len(upcoming_invoices),
        "recent_activities": recent_activities,
    })


# --- Global arama ---

@router.get("/search")
def global_search(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(default="", min_length=0),
):
    """
    Global arama endpoint'i.
    Musteriler, urunler ve faturalar arasindan arama yapar.
    JSON olarak sonuclari dondurur.
    """
    user = require_login(request, db)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Giris yapmaniz gerekiyor"})

    results = {"customers": [], "products": [], "invoices": []}

    if not q or len(q.strip()) < 2:
        return JSONResponse(content=results)

    search_term = f"%{q.strip()}%"

    # Musteri aramasi: sirket adi, ilgili kisi, email
    from sqlalchemy import or_
    from kolayis.models.customer import Customer
    from kolayis.models.product import Product
    from kolayis.models.invoice import Invoice

    customers = (
        db.query(Customer)
        .filter(
            Customer.owner_id == user.id,
            or_(
                Customer.company_name.ilike(search_term),
                Customer.contact_name.ilike(search_term),
                Customer.email.ilike(search_term),
            ),
        )
        .limit(5)
        .all()
    )
    for c in customers:
        results["customers"].append({
            "id": str(c.id),
            "title": c.company_name,
            "subtitle": c.contact_name or "",
            "link": f"/customers/{c.id}",
        })

    # Urun aramasi: urun adi, aciklama
    products = (
        db.query(Product)
        .filter(
            Product.owner_id == user.id,
            or_(
                Product.name.ilike(search_term),
                Product.description.ilike(search_term),
            ),
        )
        .limit(5)
        .all()
    )
    for p in products:
        results["products"].append({
            "id": str(p.id),
            "title": p.name,
            "subtitle": f"{p.unit_price} TL",
            "link": f"/products/{p.id}/edit",
        })

    # Fatura aramasi: fatura numarasi, musteri adi
    invoices = (
        db.query(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .filter(
            Invoice.owner_id == user.id,
            or_(
                Invoice.invoice_number.ilike(search_term),
                Customer.company_name.ilike(search_term),
            ),
        )
        .limit(5)
        .all()
    )
    for inv in invoices:
        results["invoices"].append({
            "id": str(inv.id),
            "title": inv.invoice_number,
            "subtitle": inv.customer.company_name,
            "link": f"/invoices/{inv.id}",
        })

    return JSONResponse(content=results)


# --- Musteri sayfalari ---

@router.get("/customers", response_class=HTMLResponse)
def customer_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    """Musteri listesi sayfasi"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customers, total = customer_service.get_customers(
        db, user.id, page=page, size=20, search=search, customer_status=status,
    )

    return templates.TemplateResponse("customers/list.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
        "customers": customers,
        "total": total,
        "page": page,
        "size": 20,
        "search": search,
        "status_filter": status,
    })


@router.get("/customers/new", response_class=HTMLResponse)
def customer_new(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Yeni musteri formu"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse("customers/form.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
        "customer": None,
    })


@router.post("/customers/new", response_class=HTMLResponse)
def customer_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    company_name: str = Form(...),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_number: str = Form(""),
    status: str = Form("active"),
):
    """Yeni musteri olustur"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    data = CustomerCreate(
        company_name=company_name,
        contact_name=contact_name or None,
        email=email or None,
        phone=phone or None,
        address=address or None,
        tax_number=tax_number or None,
        status=status,
    )
    customer = customer_service.create_customer(db, user.id, data)
    notification_service.create_notification(
        db, user.id, "customer_new",
        "Yeni musteri eklendi!",
        f"{company_name} basariyla musteri listenize eklendi.",
        entity_type="customer", entity_id=customer.id,
        link=f"/customers/{customer.id}",
    )
    db.commit()
    return RedirectResponse(url=f"/customers/{customer.id}", status_code=303)


@router.get("/customers/import", response_class=HTMLResponse)
def customer_import_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri CSV import formu"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse("customers/import.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
    })


@router.post("/customers/import", response_class=HTMLResponse)
async def customer_import_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """CSV veya Excel dosyasindan musteri iceri aktar"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()
    file = form.get("file")

    if not file or not file.filename:
        return templates.TemplateResponse("customers/import.html", {
            "request": request, "user": user, "active_page": "customers",
            "error": "Lutfen bir dosya secin.",
        })

    try:
        raw_bytes = await file.read()
        rows = import_service.parse_file(file.filename, raw_bytes)
    except Exception:
        return templates.TemplateResponse("customers/import.html", {
            "request": request, "user": user, "active_page": "customers",
            "error": "Dosya okunamadi. Lutfen gecerli bir CSV veya Excel dosyasi yukleyin.",
        })

    if len(rows) < 2:
        return templates.TemplateResponse("customers/import.html", {
            "request": request, "user": user, "active_page": "customers",
            "error": "Dosya bos veya sadece baslik satiri iceriyor.",
        })

    result = import_service.import_customers(db, user.id, rows)

    return templates.TemplateResponse("customers/import.html", {
        "request": request, "user": user, "active_page": "customers",
        "result": result,
    })


@router.get("/customers/import/sample")
def customer_import_sample(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Ornek musteri CSV dosyasi indir"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    import csv
    from io import StringIO
    from starlette.responses import Response

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Sirket Adi", "Ilgili Kisi", "Email", "Telefon", "Adres", "Vergi No"])
    writer.writerow(["ABC Ltd", "Ali Yilmaz", "ali@abc.com", "0532-111-2233", "Istanbul", "1234567890"])
    writer.writerow(["XYZ Bilisim", "Ayse Demir", "ayse@xyz.com", "0533-222-3344", "Ankara", "9876543210"])
    writer.writerow(["Ornek Ticaret", "Mehmet Kaya", "mehmet@ornek.com", "0534-333-4455", "Izmir", "5678901234"])

    # UTF-8 BOM ekle (Excel uyumlulugu icin)
    csv_content = "\ufeff" + output.getvalue()

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ornek_musteriler.csv"'},
    )


@router.get("/customers/export")
def customers_export(
    request: Request, db: Annotated[Session, Depends(get_db)],
    format: str = Query(default="csv"),
):
    """Musteri listesini CSV veya Excel olarak indir."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customers, _ = customer_service.get_customers(db, user.id, size=10000)

    if format == "excel":
        from openpyxl import Workbook
        from io import BytesIO

        wb = Workbook()
        ws = wb.active
        ws.title = "Musteriler"
        ws.append(["Sirket Adi", "Ilgili Kisi", "Email", "Telefon", "Adres", "Vergi No", "Durum", "Olusturma Tarihi"])
        for c in customers:
            ws.append([
                c.company_name, c.contact_name or "", c.email or "", c.phone or "",
                c.address or "", c.tax_number or "", c.status,
                c.created_at.strftime("%d.%m.%Y"),
            ])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="musteriler.xlsx"'},
        )
    else:
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Sirket Adi", "Ilgili Kisi", "Email", "Telefon", "Adres", "Vergi No", "Durum", "Olusturma Tarihi"])
        for c in customers:
            writer.writerow([
                c.company_name, c.contact_name or "", c.email or "", c.phone or "",
                c.address or "", c.tax_number or "", c.status,
                c.created_at.strftime("%d.%m.%Y"),
            ])

        from starlette.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="musteriler.csv"'},
        )


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri detay sayfasi"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customer = customer_service.get_customer(db, customer_id, user.id)
    notes = note_service.get_notes(db, customer_id, user.id)
    custom_fields = custom_field_service.get_fields_with_values(db, user.id, "customer", customer_id)

    return templates.TemplateResponse("customers/detail.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
        "customer": customer,
        "notes": notes,
        "custom_fields": custom_fields,
    })


@router.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
def customer_edit(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri duzenleme formu"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customer = customer_service.get_customer(db, customer_id, user.id)
    custom_fields = custom_field_service.get_fields_with_values(db, user.id, "customer", customer_id)

    return templates.TemplateResponse("customers/form.html", {
        "request": request,
        "user": user,
        "active_page": "customers",
        "customer": customer,
        "custom_fields": custom_fields,
    })


@router.post("/customers/{customer_id}/edit", response_class=HTMLResponse)
def customer_update(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    company_name: str = Form(...),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    tax_number: str = Form(""),
    status: str = Form("active"),
):
    """Musteri guncelle"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    data = CustomerUpdate(
        company_name=company_name,
        contact_name=contact_name or None,
        email=email or None,
        phone=phone or None,
        address=address or None,
        tax_number=tax_number or None,
        status=status,
    )
    customer_service.update_customer(db, customer_id, user.id, data)
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/customers/{customer_id}/custom-fields")
async def customer_save_custom_fields(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri ozel alan degerlerini kaydet."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form_data = await request.form()
    cf_values = {k.replace("cf_", ""): v for k, v in form_data.items() if k.startswith("cf_")}
    if cf_values:
        custom_field_service.save_values(db, customer_id, cf_values)

    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/customers/{customer_id}/delete")
def customer_delete(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri sil"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customer_service.delete_customer(db, customer_id, user.id)
    return RedirectResponse(url="/customers", status_code=303)


# --- Not islemleri ---

@router.post("/customers/{customer_id}/notes")
def note_create(
    customer_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    title: str = Form(...),
    content: str = Form(...),
    note_type: str = Form("other"),
):
    """Musteriye not ekle"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    data = NoteCreate(title=title, content=content, note_type=note_type)
    note_service.create_note(db, customer_id, user.id, data)
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/customers/{customer_id}/notes/{note_id}/delete")
def note_delete(
    customer_id: uuid.UUID,
    note_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Notu sil"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    note_service.delete_note(db, customer_id, note_id, user.id)
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


# --- Urun sayfalari ---

@router.get("/products", response_class=HTMLResponse)
def product_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    products, total = product_service.get_products(db, user.id, page=page, size=20)
    return templates.TemplateResponse("products/list.html", {
        "request": request, "user": user, "active_page": "products",
        "products": products, "total": total, "page": page, "size": 20,
    })


@router.get("/products/new", response_class=HTMLResponse)
def product_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("products/form.html", {
        "request": request, "user": user, "active_page": "products", "product": None,
    })


@router.post("/products/new")
def product_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(...),
    description: str = Form(""),
    unit_price: str = Form(...),
    unit: str = Form("adet"),
    tax_rate: int = Form(20),
    stock: str = Form(""),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from decimal import Decimal
    data = ProductCreate(
        name=name, description=description or None,
        unit_price=Decimal(unit_price), unit=unit, tax_rate=tax_rate,
        stock=int(stock) if stock else None,
    )
    product_service.create_product(db, user.id, data)
    return RedirectResponse(url="/products", status_code=303)


@router.get("/products/import", response_class=HTMLResponse)
def product_import_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Urun CSV import formu"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse("products/import.html", {
        "request": request,
        "user": user,
        "active_page": "products",
    })


@router.post("/products/import", response_class=HTMLResponse)
async def product_import_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """CSV veya Excel dosyasindan urun iceri aktar"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()
    file = form.get("file")

    if not file or not file.filename:
        return templates.TemplateResponse("products/import.html", {
            "request": request, "user": user, "active_page": "products",
            "error": "Lutfen bir dosya secin.",
        })

    try:
        raw_bytes = await file.read()
        rows = import_service.parse_file(file.filename, raw_bytes)
    except Exception:
        return templates.TemplateResponse("products/import.html", {
            "request": request, "user": user, "active_page": "products",
            "error": "Dosya okunamadi. Lutfen gecerli bir CSV veya Excel dosyasi yukleyin.",
        })

    if len(rows) < 2:
        return templates.TemplateResponse("products/import.html", {
            "request": request, "user": user, "active_page": "products",
            "error": "Dosya bos veya sadece baslik satiri iceriyor.",
        })

    result = import_service.import_products(db, user.id, rows)

    return templates.TemplateResponse("products/import.html", {
        "request": request, "user": user, "active_page": "products",
        "result": result,
    })


@router.get("/products/import/sample")
def product_import_sample(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Ornek urun CSV dosyasi indir"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    import csv
    from io import StringIO
    from starlette.responses import Response

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Urun Adi", "Aciklama", "Birim Fiyat", "Birim", "KDV Orani", "Stok"])
    writer.writerow(["Web Sitesi", "Kurumsal web sitesi", "15000", "adet", "20", ""])
    writer.writerow(["Logo Tasarim", "Profesyonel logo tasarimi", "5000", "adet", "20", ""])
    writer.writerow(["SEO Hizmeti", "Aylik SEO optimizasyonu", "3000", "ay", "20", ""])

    # UTF-8 BOM ekle (Excel uyumlulugu icin)
    csv_content = "\ufeff" + output.getvalue()

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ornek_urunler.csv"'},
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def product_edit(product_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    product = product_service.get_product(db, product_id, user.id)
    return templates.TemplateResponse("products/form.html", {
        "request": request, "user": user, "active_page": "products", "product": product,
    })


@router.post("/products/{product_id}/edit")
def product_update(
    product_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
    name: str = Form(...), description: str = Form(""), unit_price: str = Form(...),
    unit: str = Form("adet"), tax_rate: int = Form(20), stock: str = Form(""),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from decimal import Decimal
    data = ProductUpdate(
        name=name, description=description or None,
        unit_price=Decimal(unit_price), unit=unit, tax_rate=tax_rate,
        stock=int(stock) if stock else None,
    )
    product_service.update_product(db, product_id, user.id, data)
    return RedirectResponse(url="/products", status_code=303)


@router.post("/products/{product_id}/delete")
def product_delete(product_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    product_service.delete_product(db, product_id, user.id)
    return RedirectResponse(url="/products", status_code=303)


# --- Raporlar sayfasi ---

@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    """Detayli raporlar sayfasi"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from datetime import date, datetime, timedelta
    from decimal import Decimal
    from collections import defaultdict
    from sqlalchemy import func as sqlfunc
    from kolayis.models.invoice import Invoice, InvoiceItem
    from kolayis.models.customer import Customer

    # Tarih filtresi
    date_filter_start = None
    date_filter_end = None
    if start_date:
        try:
            date_filter_start = date.fromisoformat(start_date)
        except ValueError:
            start_date = None
    if end_date:
        try:
            date_filter_end = date.fromisoformat(end_date)
        except ValueError:
            end_date = None

    # Tum faturalari getir (filtreli)
    query = db.query(Invoice).filter(Invoice.owner_id == user.id)
    if date_filter_start:
        query = query.filter(Invoice.invoice_date >= date_filter_start)
    if date_filter_end:
        query = query.filter(Invoice.invoice_date <= date_filter_end)
    all_invoices = query.all()

    # Temel istatistikler
    total_revenue = float(sum(inv.total for inv in all_invoices))
    paid_total = float(sum(inv.total for inv in all_invoices if inv.status == "paid"))
    unpaid_total = float(sum(inv.total for inv in all_invoices if inv.status in ("draft", "sent")))
    total_invoice_count = len(all_invoices)

    # Fatura durum dagilimi
    status_distribution = {}
    for inv in all_invoices:
        status_distribution[inv.status] = status_distribution.get(inv.status, 0) + 1

    # Son 12 ayin aylik gelir verisi (odenmis faturalardan)
    now = datetime.utcnow()
    twelve_months_ago = now.replace(day=1) - timedelta(days=30 * 11)
    twelve_months_ago = twelve_months_ago.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rev_query = (
        db.query(
            sqlfunc.to_char(Invoice.invoice_date, 'YYYY-MM').label('month'),
            sqlfunc.coalesce(sqlfunc.sum(Invoice.total), 0).label('revenue'),
        )
        .filter(
            Invoice.owner_id == user.id,
            Invoice.status == 'paid',
            Invoice.invoice_date >= twelve_months_ago,
        )
    )
    if date_filter_start:
        rev_query = rev_query.filter(Invoice.invoice_date >= date_filter_start)
    if date_filter_end:
        rev_query = rev_query.filter(Invoice.invoice_date <= date_filter_end)

    rev_rows = (
        rev_query
        .group_by(sqlfunc.to_char(Invoice.invoice_date, 'YYYY-MM'))
        .order_by(sqlfunc.to_char(Invoice.invoice_date, 'YYYY-MM'))
        .all()
    )
    monthly_revenue = [{"month": r.month, "revenue": float(r.revenue)} for r in rev_rows]

    # En cok fatura kesilen musteriler (Top 5) - gelire gore siralama
    customer_stats = defaultdict(lambda: {"company_name": "", "invoice_count": 0, "total_revenue": 0.0})
    for inv in all_invoices:
        cid = str(inv.customer_id)
        customer_stats[cid]["company_name"] = inv.customer.company_name
        customer_stats[cid]["invoice_count"] += 1
        customer_stats[cid]["total_revenue"] += float(inv.total)

    top_customers = sorted(customer_stats.values(), key=lambda x: x["total_revenue"], reverse=True)[:5]

    # Musteri basina ortalama gelir
    unique_customer_count = len(customer_stats)
    avg_revenue_per_customer = total_revenue / unique_customer_count if unique_customer_count > 0 else 0

    # En cok satilan urunler (Top 5) - fatura kalemleri uzerinden
    product_stats = defaultdict(lambda: {"description": "", "total_qty": 0.0, "total_revenue": 0.0})
    for inv in all_invoices:
        for item in inv.items:
            desc = item.description
            product_stats[desc]["description"] = desc
            product_stats[desc]["total_qty"] += float(item.quantity)
            product_stats[desc]["total_revenue"] += float(item.line_total)

    top_products = sorted(product_stats.values(), key=lambda x: x["total_revenue"], reverse=True)[:5]

    return templates.TemplateResponse("reports.html", {
        "request": request,
        "user": user,
        "active_page": "reports",
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "total_invoice_count": total_invoice_count,
        "status_distribution": status_distribution,
        "monthly_revenue": monthly_revenue,
        "top_customers": top_customers,
        "avg_revenue_per_customer": avg_revenue_per_customer,
        "top_products": top_products,
    })


# --- Fatura sayfalari ---

@router.get("/invoices", response_class=HTMLResponse)
def invoice_list(
    request: Request, db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    status: str | None = Query(default=None),
    sort: str | None = Query(default=None),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoices, total = invoice_service.get_invoices(db, user.id, invoice_status=status, page=page, size=20, sort=sort)

    from datetime import date as date_cls
    today = date_cls.today()

    return templates.TemplateResponse("invoices/list.html", {
        "request": request, "user": user, "active_page": "invoices",
        "invoices": invoices, "status_filter": status,
        "total": total, "page": page, "size": 20,
        "today": today, "sort": sort,
    })


@router.get("/invoices/new", response_class=HTMLResponse)
def invoice_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    customers, _ = customer_service.get_customers(db, user.id, size=100)
    products, _ = product_service.get_products(db, user.id, size=10000)
    from datetime import date
    return templates.TemplateResponse("invoices/new.html", {
        "request": request, "user": user, "active_page": "invoices",
        "customers": customers, "products": products, "today": date.today().isoformat(),
    })


@router.post("/invoices/new")
async def invoice_create(
    request: Request, db: Annotated[Session, Depends(get_db)],
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()
    from decimal import Decimal
    from datetime import date

    # Fatura kalemleri
    descriptions = form.getlist("item_description[]")
    quantities = form.getlist("item_quantity[]")
    unit_prices = form.getlist("item_unit_price[]")
    tax_rates = form.getlist("item_tax_rate[]")

    items = []
    for i in range(len(descriptions)):
        if descriptions[i] and unit_prices[i]:
            items.append(InvoiceItemCreate(
                description=descriptions[i],
                quantity=Decimal(quantities[i]),
                unit_price=Decimal(unit_prices[i]),
                tax_rate=int(tax_rates[i]),
            ))

    due_date_str = form.get("due_date")
    data = InvoiceCreate(
        customer_id=uuid.UUID(form.get("customer_id")),
        invoice_date=date.fromisoformat(form.get("invoice_date")),
        due_date=date.fromisoformat(due_date_str) if due_date_str else None,
        notes=form.get("notes") or None,
        items=items,
    )
    invoice = invoice_service.create_invoice(db, user.id, data)
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)


@router.get("/invoices/export")
def invoices_export(
    request: Request, db: Annotated[Session, Depends(get_db)],
    format: str = Query(default="csv"),
):
    """Fatura listesini CSV veya Excel olarak indir."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    invoices, _ = invoice_service.get_invoices(db, user.id, size=10000)

    if format == "excel":
        from openpyxl import Workbook
        from io import BytesIO

        wb = Workbook()
        ws = wb.active
        ws.title = "Faturalar"
        ws.append(["Fatura No", "Musteri", "Tarih", "Vade", "Durum", "Ara Toplam", "KDV", "Genel Toplam"])
        for inv in invoices:
            ws.append([
                inv.invoice_number, inv.customer.company_name,
                inv.invoice_date.strftime("%d.%m.%Y"),
                inv.due_date.strftime("%d.%m.%Y") if inv.due_date else "",
                inv.status, float(inv.subtotal), float(inv.tax_total), float(inv.total),
            ])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="faturalar.xlsx"'},
        )
    else:
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Fatura No", "Musteri", "Tarih", "Vade", "Durum", "Ara Toplam", "KDV", "Genel Toplam"])
        for inv in invoices:
            writer.writerow([
                inv.invoice_number, inv.customer.company_name,
                inv.invoice_date.strftime("%d.%m.%Y"),
                inv.due_date.strftime("%d.%m.%Y") if inv.due_date else "",
                inv.status, float(inv.subtotal), float(inv.tax_total), float(inv.total),
            ])

        from starlette.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="faturalar.csv"'},
        )


@router.get("/invoices/import", response_class=HTMLResponse)
def invoice_import_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Fatura import formu"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse("invoices/import.html", {
        "request": request,
        "user": user,
        "active_page": "invoices",
    })


@router.post("/invoices/import", response_class=HTMLResponse)
async def invoice_import_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """CSV veya Excel dosyasindan fatura iceri aktar"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    form = await request.form()
    file = form.get("file")

    if not file or not file.filename:
        return templates.TemplateResponse("invoices/import.html", {
            "request": request, "user": user, "active_page": "invoices",
            "error": "Lutfen bir dosya secin.",
        })

    try:
        raw_bytes = await file.read()
        rows = import_service.parse_file(file.filename, raw_bytes)
    except Exception:
        return templates.TemplateResponse("invoices/import.html", {
            "request": request, "user": user, "active_page": "invoices",
            "error": "Dosya okunamadi. Lutfen gecerli bir CSV veya Excel dosyasi yukleyin.",
        })

    if len(rows) < 2:
        return templates.TemplateResponse("invoices/import.html", {
            "request": request, "user": user, "active_page": "invoices",
            "error": "Dosya bos veya sadece baslik satiri iceriyor.",
        })

    result = import_service.import_invoices(db, user.id, rows)

    return templates.TemplateResponse("invoices/import.html", {
        "request": request, "user": user, "active_page": "invoices",
        "result": result,
    })


@router.get("/invoices/import/sample")
def invoice_import_sample(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Ornek fatura CSV dosyasi indir"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    import csv
    from io import StringIO
    from starlette.responses import Response

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Musteri Adi", "Fatura Tarihi", "Vade Tarihi", "Kalem Aciklama", "Miktar", "Birim Fiyat", "KDV Orani"])
    # Tek kalemli fatura ornegi
    writer.writerow(["ABC Ltd", "2026-02-01", "2026-03-01", "Web Sitesi Tasarimi", "1", "15000", "20"])
    # Cok kalemli fatura ornegi (ayni musteri + tarih = tek fatura)
    writer.writerow(["XYZ Bilisim", "2026-02-05", "2026-03-05", "Logo Tasarim", "1", "5000", "20"])
    writer.writerow(["XYZ Bilisim", "2026-02-05", "2026-03-05", "Kartvizit Basim", "500", "3", "20"])
    writer.writerow(["XYZ Bilisim", "2026-02-05", "2026-03-05", "SEO Hizmeti", "1", "3000", "20"])

    csv_content = "\ufeff" + output.getvalue()

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ornek_faturalar.csv"'},
    )


@router.get("/invoices/{invoice_id}/edit", response_class=HTMLResponse)
def invoice_edit(invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Fatura duzenleme formu (sadece draft ve sent durumunda)"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice = invoice_service.get_invoice(db, invoice_id, user.id)
    if invoice.status not in ("draft", "sent"):
        return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)
    customers, _ = customer_service.get_customers(db, user.id, size=100)
    return templates.TemplateResponse("invoices/edit.html", {
        "request": request, "user": user, "active_page": "invoices",
        "invoice": invoice, "customers": customers,
    })


@router.post("/invoices/{invoice_id}/edit")
def invoice_update(
    invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
    customer_id: str = Form(...),
    invoice_date: str = Form(...),
    due_date: str = Form(""),
    notes: str = Form(""),
):
    """Fatura bilgilerini guncelle"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from datetime import date
    data = InvoiceUpdate(
        customer_id=uuid.UUID(customer_id),
        invoice_date=date.fromisoformat(invoice_date),
        due_date=date.fromisoformat(due_date) if due_date else None,
        notes=notes or None,
    )
    invoice_service.update_invoice(db, invoice_id, user.id, data)
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/duplicate")
def invoice_duplicate(
    invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
):
    """Mevcut faturayi kopyalayarak yeni bir taslak fatura olustur."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from datetime import date
    from decimal import Decimal

    # Mevcut faturayi oku
    source_invoice = invoice_service.get_invoice(db, invoice_id, user.id)

    # Kalemleri kopyala
    items = [
        InvoiceItemCreate(
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
        )
        for item in source_invoice.items
    ]

    # Yeni fatura olustur (bugunun tarihiyle, taslak olarak)
    data = InvoiceCreate(
        customer_id=source_invoice.customer_id,
        invoice_date=date.today(),
        due_date=None,
        status="draft",
        notes=f"{source_invoice.invoice_number} numarali faturadan kopyalandi",
        items=items,
    )
    new_invoice = invoice_service.create_invoice(db, user.id, data)
    return RedirectResponse(url=f"/invoices/{new_invoice.id}", status_code=303)


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def invoice_detail(invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice = invoice_service.get_invoice(db, invoice_id, user.id)

    from datetime import date as date_cls
    today = date_cls.today()

    return templates.TemplateResponse("invoices/detail.html", {
        "request": request, "user": user, "active_page": "invoices", "invoice": invoice,
        "today": today,
    })


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Faturanin PDF ciktisini indir."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    invoice = invoice_service.get_invoice(db, invoice_id, user.id)

    # HTML sablonu render et
    html_content = templates.get_template("invoices/pdf.html").render(invoice=invoice)

    # HTML'den PDF olustur
    from io import BytesIO
    from xhtml2pdf import pisa

    pdf_buffer = BytesIO()
    pisa.CreatePDF(html_content, dest=pdf_buffer)
    pdf_buffer.seek(0)

    filename = f"{invoice.invoice_number}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/invoices/{invoice_id}/status")
def invoice_status_update(
    invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
    status: str = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice_service.update_invoice_status(db, invoice_id, user.id, status)
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/items")
def invoice_add_item(
    invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
    description: str = Form(...), quantity: str = Form(...),
    unit_price: str = Form(...), tax_rate: int = Form(20),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from decimal import Decimal
    data = InvoiceItemCreate(
        description=description, quantity=Decimal(quantity),
        unit_price=Decimal(unit_price), tax_rate=tax_rate,
    )
    invoice_service.add_invoice_item(db, invoice_id, user.id, data)
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/items/{item_id}/delete")
def invoice_remove_item(
    invoice_id: uuid.UUID, item_id: uuid.UUID,
    request: Request, db: Annotated[Session, Depends(get_db)],
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice_service.remove_invoice_item(db, invoice_id, item_id, user.id)
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/delete")
def invoice_delete(invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice_service.delete_invoice(db, invoice_id, user.id)
    return RedirectResponse(url="/invoices", status_code=303)


# --- Fatura odeme islemleri ---

@router.post("/invoices/{invoice_id}/payments")
def payment_create(
    invoice_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    amount: str = Form(...),
    payment_date: str = Form(...),
    payment_method: str = Form("bank_transfer"),
    notes: str = Form(""),
):
    """Faturaya odeme ekle"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from decimal import Decimal
    from datetime import date

    data = PaymentCreate(
        amount=Decimal(amount),
        payment_date=date.fromisoformat(payment_date),
        payment_method=payment_method,
        notes=notes or None,
    )

    try:
        payment = payment_service.create_payment(db, invoice_id, user.id, data)
        # Odeme bildirimi
        from kolayis.models.invoice import Invoice
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            notification_service.create_notification(
                db, user.id, "payment_received",
                "Odeme alindi!",
                f"{invoice.invoice_number} faturasina {amount} TL odeme kaydedildi.",
                entity_type="invoice", entity_id=invoice_id,
                link=f"/invoices/{invoice_id}",
            )
            # Fatura tamamen odendiyse ek bildirim
            if invoice.status == "paid":
                notification_service.create_notification(
                    db, user.id, "invoice_paid",
                    "Fatura tamamen odendi!",
                    f"{invoice.invoice_number} faturasi tamamen odendi. Toplam: {invoice.total:.2f} TL",
                    entity_type="invoice", entity_id=invoice_id,
                    link=f"/invoices/{invoice_id}",
                )
            db.commit()
    except HTTPException:
        # Validation hatasi durumunda fatura detay sayfasina don
        pass

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/invoices/{invoice_id}/payments/{payment_id}/delete")
def payment_delete(
    invoice_id: uuid.UUID,
    payment_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Odeme sil"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    payment_service.delete_payment(db, payment_id, invoice_id, user.id)
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


# --- Fatura email gonderme ---

@router.post("/invoices/{invoice_id}/send-email")
def invoice_send_email(
    invoice_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
):
    """Fatura PDF'ini musteri email adresine gonder."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    invoice = invoice_service.get_invoice(db, invoice_id, user.id)

    if not invoice.customer.email:
        # Email yok, geri don
        return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)

    # PDF olustur
    html_content = templates.get_template("invoices/pdf.html").render(invoice=invoice)
    from io import BytesIO
    from xhtml2pdf import pisa
    pdf_buffer = BytesIO()
    pisa.CreatePDF(html_content, dest=pdf_buffer)
    pdf_bytes = pdf_buffer.getvalue()

    # Email gonder
    success = email_service.send_invoice_email(
        to_email=invoice.customer.email,
        customer_name=invoice.customer.company_name,
        invoice_number=invoice.invoice_number,
        pdf_bytes=pdf_bytes,
    )

    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


# --- Vadesi gecen fatura sayisi API (sidebar badge icin) ---

@router.get("/api/overdue-count")
def overdue_count_api(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Sidebar badge icin vadesi gecen fatura sayisini JSON olarak dondur."""
    user = require_login(request, db)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"count": 0})

    from datetime import date as date_cls
    today = date_cls.today()
    all_invoices, _ = invoice_service.get_invoices(db, user.id, size=10000)
    overdue_count = sum(
        1 for inv in all_invoices
        if inv.due_date and inv.status in ("sent", "draft") and inv.due_date < today
    )
    from fastapi.responses import JSONResponse
    return JSONResponse({"count": overdue_count})


# --- Aktivite sayfasi ---

@router.get("/activities", response_class=HTMLResponse)
def activities_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
):
    """Tum aktiviteleri listele (sayfalama destekli)"""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    activities, total = activity_service.get_activities_paginated(
        db, user.id, page=page, size=20, action=action, entity_type=entity_type,
    )

    return templates.TemplateResponse("activities.html", {
        "request": request,
        "user": user,
        "active_page": "activities",
        "activities": activities,
        "total": total,
        "page": page,
        "size": 20,
        "action_filter": action,
        "entity_type_filter": entity_type,
    })


# --- Ayarlar sayfasi ---

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "active_page": "settings",
        "email_configured": email_service.is_email_configured(),
    })


@router.post("/settings/profile")
def settings_update_profile(
    request: Request, db: Annotated[Session, Depends(get_db)],
    full_name: str = Form(...), email: str = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Email benzersizlik kontrolu
    existing = db.query(User).filter(User.email == email, User.id != user.id).first()
    if existing:
        return templates.TemplateResponse("settings.html", {
            "request": request, "user": user, "active_page": "settings",
            "email_configured": email_service.is_email_configured(),
            "error": "Bu email adresi baska bir hesapta kullaniliyor",
        })

    user.full_name = full_name
    user.email = email
    db.commit()
    db.refresh(user)

    return templates.TemplateResponse("settings.html", {
        "request": request, "user": user, "active_page": "settings",
        "email_configured": email_service.is_email_configured(),
        "success": "Profil bilgileri guncellendi",
    })


@router.post("/settings/password")
def settings_change_password(
    request: Request, db: Annotated[Session, Depends(get_db)],
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    ctx = {
        "request": request, "user": user, "active_page": "settings",
        "email_configured": email_service.is_email_configured(),
    }

    if not verify_password(current_password, user.hashed_password):
        ctx["error"] = "Mevcut sifre hatali"
        return templates.TemplateResponse("settings.html", ctx)

    if len(new_password) < 8:
        ctx["error"] = "Yeni sifre en az 8 karakter olmali"
        return templates.TemplateResponse("settings.html", ctx)

    if new_password != new_password_confirm:
        ctx["error"] = "Yeni sifreler eslesmiyor"
        return templates.TemplateResponse("settings.html", ctx)

    user.hashed_password = hash_password(new_password)
    db.commit()

    ctx["success"] = "Sifre basariyla degistirildi"
    return templates.TemplateResponse("settings.html", ctx)


# --- Teklif (Quotation) sayfalari ---

@router.get("/quotations", response_class=HTMLResponse)
def quotations_list(request: Request, db: Annotated[Session, Depends(get_db)], search: str = "", status: str = "", sort: str = "-date", page: int = 1):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    size = 20
    skip = (page - 1) * size
    quotations, total = quotation_service.get_quotations(db, user.id, skip=skip, limit=size, search=search, status_filter=status, sort=sort)
    return templates.TemplateResponse("quotations/list.html", {
        "request": request, "user": user, "active_page": "quotations",
        "quotations": quotations, "total": total, "page": page, "size": size,
        "search": search, "status_filter": status, "sort": sort,
    })

@router.get("/quotations/new", response_class=HTMLResponse)
def quotation_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    customers, _ = customer_service.get_customers(db, user.id)
    products, _ = product_service.get_products(db, user.id)
    return templates.TemplateResponse("quotations/form.html", {
        "request": request, "user": user, "active_page": "quotations",
        "customers": customers, "products": products,
    })

@router.post("/quotations/new")
def quotation_create(request: Request, db: Annotated[Session, Depends(get_db)],
    customer_id: uuid.UUID = Form(...), quotation_date: str = Form(...),
    valid_until: str = Form(""), notes: str = Form(""),
    descriptions: list[str] = Form(...), quantities: list[str] = Form(...),
    unit_prices: list[str] = Form(...), tax_rates: list[str] = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from datetime import date as date_type
    from decimal import Decimal
    from kolayis.schemas.quotation import QuotationItemCreate
    items = []
    for i in range(len(descriptions)):
        if descriptions[i].strip():
            items.append(QuotationItemCreate(
                description=descriptions[i], quantity=Decimal(quantities[i]),
                unit_price=Decimal(unit_prices[i]), tax_rate=int(tax_rates[i]),
            ))
    data = QuotationCreate(
        customer_id=customer_id,
        quotation_date=date_type.fromisoformat(quotation_date),
        valid_until=date_type.fromisoformat(valid_until) if valid_until else None,
        notes=notes or None, items=items,
    )
    q = quotation_service.create_quotation(db, user.id, data)
    activity_service.log_activity(db, user.id, "quotation", "create", str(q.id), f"Teklif olusturuldu: {q.quotation_number}")
    return RedirectResponse(url=f"/quotations/{q.id}", status_code=303)

@router.get("/quotations/{quotation_id}", response_class=HTMLResponse)
def quotation_detail(request: Request, quotation_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    q = quotation_service.get_quotation(db, quotation_id, user.id)
    if not q:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("quotations/detail.html", {
        "request": request, "user": user, "active_page": "quotations", "quotation": q,
    })

@router.post("/quotations/{quotation_id}/status")
def quotation_change_status(request: Request, quotation_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], status: str = Form(...)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    quotation_service.update_quotation(db, quotation_id, user.id, QuotationUpdate(status=status))
    return RedirectResponse(url=f"/quotations/{quotation_id}", status_code=303)

@router.post("/quotations/{quotation_id}/convert")
def quotation_convert_to_invoice(request: Request, quotation_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    invoice = quotation_service.convert_to_invoice(db, quotation_id, user.id)
    if not invoice:
        raise HTTPException(status_code=404)
    activity_service.log_activity(db, user.id, "quotation", "convert", str(quotation_id), f"Teklif faturaya cevirildi: {invoice.invoice_number}")
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)

@router.post("/quotations/{quotation_id}/delete")
def quotation_delete(request: Request, quotation_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    quotation_service.delete_quotation(db, quotation_id, user.id)
    return RedirectResponse(url="/quotations", status_code=303)


# --- Gelir-Gider sayfalari ---

@router.get("/expenses", response_class=HTMLResponse)
def expenses_list(request: Request, db: Annotated[Session, Depends(get_db)], expense_type: str = "", category_id: str = "", start_date: str = "", end_date: str = "", page: int = 1):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from datetime import date as d
    size = 20
    sd = d.fromisoformat(start_date) if start_date else None
    ed = d.fromisoformat(end_date) if end_date else None
    cat_id = uuid.UUID(category_id) if category_id else None
    expenses, total = expense_service.get_expenses(db, user.id, page=page, size=size, expense_type=expense_type or None, category_id=cat_id, start_date=sd, end_date=ed)
    categories = expense_service.get_expense_categories(db, user.id)
    summary = expense_service.get_expense_summary(db, user.id, start_date=sd, end_date=ed)
    return templates.TemplateResponse("expenses/list.html", {
        "request": request, "user": user, "active_page": "expenses",
        "expenses": expenses, "total": total, "page": page, "size": size,
        "categories": categories, "summary": summary,
        "expense_type": expense_type, "category_id": category_id,
        "start_date": start_date, "end_date": end_date,
    })

@router.get("/expenses/new", response_class=HTMLResponse)
def expense_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    categories = expense_service.get_expense_categories(db, user.id)
    return templates.TemplateResponse("expenses/form.html", {
        "request": request, "user": user, "active_page": "expenses", "categories": categories,
    })

@router.post("/expenses/new")
def expense_create(request: Request, db: Annotated[Session, Depends(get_db)],
    description: str = Form(...), amount: str = Form(...), expense_date: str = Form(...),
    expense_type: str = Form(...), category_id: str = Form(""), payment_method: str = Form(""), notes: str = Form(""),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from datetime import date as d
    from decimal import Decimal
    data = ExpenseCreate(
        description=description, amount=Decimal(amount),
        expense_date=d.fromisoformat(expense_date), expense_type=expense_type,
        category_id=uuid.UUID(category_id) if category_id else None,
        payment_method=payment_method or None, notes=notes or None,
    )
    exp = expense_service.create_expense(db, user.id, data)
    activity_service.log_activity(db, user.id, "expense", "create", str(exp.id), f"{'Gelir' if expense_type == 'income' else 'Gider'} eklendi: {description}")
    return RedirectResponse(url="/expenses", status_code=303)

@router.post("/expenses/{expense_id}/delete")
def expense_delete(request: Request, expense_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    expense_service.delete_expense(db, expense_id, user.id)
    return RedirectResponse(url="/expenses", status_code=303)

@router.get("/expenses/categories", response_class=HTMLResponse)
def expense_categories_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    categories = expense_service.get_expense_categories(db, user.id)
    return templates.TemplateResponse("expenses/categories.html", {
        "request": request, "user": user, "active_page": "expenses", "categories": categories,
    })

@router.post("/expenses/categories/new")
def expense_category_create(request: Request, db: Annotated[Session, Depends(get_db)], name: str = Form(...), color: str = Form("#6366f1")):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    expense_service.create_expense_category(db, user.id, ExpenseCategoryCreate(name=name, color=color))
    return RedirectResponse(url="/expenses/categories", status_code=303)

@router.post("/expenses/categories/{cat_id}/delete")
def expense_category_delete(request: Request, cat_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    expense_service.delete_expense_category(db, cat_id, user.id)
    return RedirectResponse(url="/expenses/categories", status_code=303)


# --- Tekrarlayan Fatura sayfalari ---

@router.get("/recurring", response_class=HTMLResponse)
def recurring_list(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    items = recurring_service.get_recurring_invoices(db, user.id)
    return templates.TemplateResponse("recurring/list.html", {
        "request": request, "user": user, "active_page": "recurring", "recurring_invoices": items,
    })

@router.get("/recurring/new", response_class=HTMLResponse)
def recurring_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    customers, _ = customer_service.get_customers(db, user.id)
    products, _ = product_service.get_products(db, user.id)
    return templates.TemplateResponse("recurring/form.html", {
        "request": request, "user": user, "active_page": "recurring",
        "customers": customers, "products": products,
    })

@router.post("/recurring/new")
def recurring_create(request: Request, db: Annotated[Session, Depends(get_db)],
    customer_id: uuid.UUID = Form(...), frequency: str = Form(...),
    start_date: str = Form(...), end_date: str = Form(""), notes: str = Form(""),
    descriptions: list[str] = Form(...), quantities: list[str] = Form(...),
    unit_prices: list[str] = Form(...), tax_rates: list[str] = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from datetime import date as d
    from decimal import Decimal
    from kolayis.schemas.recurring import RecurringItemCreate
    items = []
    for i in range(len(descriptions)):
        if descriptions[i].strip():
            items.append(RecurringItemCreate(
                description=descriptions[i], quantity=Decimal(quantities[i]),
                unit_price=Decimal(unit_prices[i]), tax_rate=int(tax_rates[i]),
            ))
    data = RecurringCreate(
        customer_id=customer_id, frequency=frequency,
        start_date=d.fromisoformat(start_date),
        end_date=d.fromisoformat(end_date) if end_date else None,
        notes=notes or None, items=items,
    )
    rec = recurring_service.create_recurring_invoice(db, user.id, data)
    activity_service.log_activity(db, user.id, "recurring", "create", str(rec.id), f"Tekrarlayan fatura olusturuldu")
    return RedirectResponse(url=f"/recurring/{rec.id}", status_code=303)

@router.get("/recurring/{rec_id}", response_class=HTMLResponse)
def recurring_detail(request: Request, rec_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    rec = recurring_service.get_recurring_invoice(db, rec_id, user.id)
    if not rec:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("recurring/detail.html", {
        "request": request, "user": user, "active_page": "recurring", "recurring": rec,
    })

@router.post("/recurring/{rec_id}/toggle")
def recurring_toggle(request: Request, rec_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    recurring_service.toggle_active(db, rec_id, user.id)
    return RedirectResponse(url=f"/recurring/{rec_id}", status_code=303)

@router.post("/recurring/{rec_id}/generate")
def recurring_generate_now(request: Request, rec_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    rec = recurring_service.get_recurring_invoice(db, rec_id, user.id)
    if not rec:
        raise HTTPException(status_code=404)
    invoice = recurring_service.generate_invoice_from_recurring(db, rec)
    activity_service.log_activity(db, user.id, "recurring", "generate", str(rec_id), f"Fatura uretildi: {invoice.invoice_number}")
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)

@router.post("/recurring/{rec_id}/delete")
def recurring_delete(request: Request, rec_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    recurring_service.delete_recurring_invoice(db, rec_id, user.id)
    return RedirectResponse(url="/recurring", status_code=303)


# --- Stok Takibi sayfalari ---

@router.get("/stock/movements", response_class=HTMLResponse)
def stock_movements(request: Request, db: Annotated[Session, Depends(get_db)], product_id: str = ""):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    pid = uuid.UUID(product_id) if product_id else None
    movements = stock_service.get_stock_movements(db, user.id, product_id=pid)
    products, _ = product_service.get_products(db, user.id)
    return templates.TemplateResponse("stock/movements.html", {
        "request": request, "user": user, "active_page": "stock",
        "movements": movements, "products": products, "product_id": product_id,
    })

@router.get("/stock/adjust", response_class=HTMLResponse)
def stock_adjust_form(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    products, _ = product_service.get_products(db, user.id)
    return templates.TemplateResponse("stock/adjust.html", {
        "request": request, "user": user, "active_page": "stock", "products": products,
    })

@router.post("/stock/adjust")
def stock_adjust_submit(request: Request, db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID = Form(...), movement_type: str = Form(...),
    quantity: int = Form(...), notes: str = Form(""),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    stock_service.add_stock_movement(db, user.id, product_id, movement_type, quantity, reference_type="manual", notes=notes or None)
    activity_service.log_activity(db, user.id, "stock", "adjust", str(product_id), f"Stok hareketi: {movement_type} {quantity}")
    # Dusuk stok kontrolu - stok 5'in altina dustuyse bildirim
    from kolayis.models.product import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if product and product.stock is not None and product.stock <= 5:
        notification_service.create_notification(
            db, user.id, "stock_low",
            "Stok uyarisi!",
            f"{product.name} urununde stok {product.stock} adet kaldi.",
            entity_type="product", entity_id=product_id,
            link=f"/stock/alerts",
        )
        db.commit()
    return RedirectResponse(url="/stock/movements", status_code=303)

@router.get("/stock/alerts", response_class=HTMLResponse)
def stock_alerts(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    low_stock = stock_service.get_low_stock_products(db, user.id)
    summary = stock_service.get_stock_summary(db, user.id)
    return templates.TemplateResponse("stock/alerts.html", {
        "request": request, "user": user, "active_page": "stock",
        "low_stock_products": low_stock, "summary": summary,
    })


# --- Webhook sayfalari ---

@router.get("/webhooks", response_class=HTMLResponse)
def webhooks_list(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    webhooks = webhook_service.get_webhooks(db, user.id)
    return templates.TemplateResponse("webhooks/list.html", {
        "request": request, "user": user, "active_page": "webhooks", "webhooks": webhooks,
    })

@router.get("/webhooks/new", response_class=HTMLResponse)
def webhook_new(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("webhooks/form.html", {
        "request": request, "user": user, "active_page": "webhooks",
    })

@router.post("/webhooks/new")
def webhook_create(request: Request, db: Annotated[Session, Depends(get_db)],
    url: str = Form(...), secret: str = Form(...), description: str = Form(""),
    events: list[str] = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    data = WebhookCreate(url=url, secret=secret, events=events, description=description or None)
    webhook_service.create_webhook(db, user.id, data)
    return RedirectResponse(url="/webhooks", status_code=303)

@router.get("/webhooks/{wh_id}/logs", response_class=HTMLResponse)
def webhook_logs(request: Request, wh_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    wh = webhook_service.get_webhook(db, wh_id, user.id)
    if not wh:
        raise HTTPException(status_code=404)
    logs = webhook_service.get_webhook_logs(db, wh_id, user.id)
    return templates.TemplateResponse("webhooks/logs.html", {
        "request": request, "user": user, "active_page": "webhooks", "webhook": wh, "logs": logs,
    })

@router.post("/webhooks/{wh_id}/delete")
def webhook_delete(request: Request, wh_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    webhook_service.delete_webhook(db, wh_id, user.id)
    return RedirectResponse(url="/webhooks", status_code=303)


# --- Takvim sayfasi ---

@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("calendar.html", {
        "request": request, "user": user, "active_page": "calendar",
    })

@router.get("/api/calendar/events")
def calendar_events_api(request: Request, db: Annotated[Session, Depends(get_db)], month: str = ""):
    user = require_login(request, db)
    if not user:
        return JSONResponse(content=[])
    from datetime import date
    if month:
        parts = month.split("-")
        year, m = int(parts[0]), int(parts[1])
    else:
        today = date.today()
        year, m = today.year, today.month
    events = calendar_service.get_calendar_events(db, user.id, year, m)
    return JSONResponse(content=events)


# --- Toplu Islemler ---

@router.post("/bulk/customers/delete")
def bulk_delete_customers(request: Request, db: Annotated[Session, Depends(get_db)], selected_ids: list[str] = Form(...)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    ids = [uuid.UUID(sid) for sid in selected_ids]
    result = bulk_service.bulk_delete_customers(db, user.id, ids)
    activity_service.log_activity(db, user.id, "bulk", "delete", "", f"Toplu musteri silme: {result.get('success', 0)} basarili")
    return templates.TemplateResponse("bulk/actions.html", {
        "request": request, "user": user, "result": result, "action": "Musteri Silme", "back_url": "/customers",
    })

@router.post("/bulk/invoices/status")
def bulk_update_invoice_status(request: Request, db: Annotated[Session, Depends(get_db)], selected_ids: list[str] = Form(...), new_status: str = Form(...)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    ids = [uuid.UUID(sid) for sid in selected_ids]
    result = bulk_service.bulk_update_invoice_status(db, user.id, ids, new_status)
    activity_service.log_activity(db, user.id, "bulk", "update", "", f"Toplu fatura durum guncelleme: {result.get('success', 0)} basarili")
    return templates.TemplateResponse("bulk/actions.html", {
        "request": request, "user": user, "result": result, "action": "Fatura Durum Guncelleme", "back_url": "/invoices",
    })

@router.post("/bulk/products/delete")
def bulk_delete_products(request: Request, db: Annotated[Session, Depends(get_db)], selected_ids: list[str] = Form(...)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    ids = [uuid.UUID(sid) for sid in selected_ids]
    result = bulk_service.bulk_delete_products(db, user.id, ids)
    activity_service.log_activity(db, user.id, "bulk", "delete", "", f"Toplu urun silme: {result.get('success', 0)} basarili")
    return templates.TemplateResponse("bulk/actions.html", {
        "request": request, "user": user, "result": result, "action": "Urun Silme", "back_url": "/products",
    })


# --- E-Fatura ---

@router.get("/invoices/{invoice_id}/einvoice", response_class=HTMLResponse)
def einvoice_preview(request: Request, invoice_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    inv = invoice_service.get_invoice(db, invoice_id, user.id)
    if not inv:
        raise HTTPException(status_code=404)
    xml_content = einvoice_service.generate_ubl_xml(inv, inv.customer, inv.items, user)
    return templates.TemplateResponse("invoices/einvoice_preview.html", {
        "request": request, "user": user, "active_page": "invoices",
        "invoice": inv, "xml_content": xml_content,
    })

@router.get("/invoices/{invoice_id}/einvoice/download")
def einvoice_download(request: Request, invoice_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    inv = invoice_service.get_invoice(db, invoice_id, user.id)
    if not inv:
        raise HTTPException(status_code=404)
    xml_content = einvoice_service.generate_ubl_xml(inv, inv.customer, inv.items, user)
    from fastapi.responses import Response
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=efatura_{inv.invoice_number}.xml"},
    )


# --- Dosya Ekleri ---

@router.post("/attachments/upload")
async def attachment_upload(request: Request, db: Annotated[Session, Depends(get_db)],
    entity_type: str = Form(...), entity_id: str = Form(...), description: str = Form(""),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="Dosya secilmedi")
    att = attachment_service.save_attachment(db, user.id, entity_type, uuid.UUID(entity_id), file, description or None)
    activity_service.log_activity(db, user.id, "attachment", "upload", str(att.id), f"Dosya yuklendi: {att.original_filename}")
    # Geldigi sayfaya geri don
    if entity_type == "customer":
        return RedirectResponse(url=f"/customers/{entity_id}", status_code=303)
    elif entity_type == "invoice":
        return RedirectResponse(url=f"/invoices/{entity_id}", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/attachments/{att_id}/download")
def attachment_download(request: Request, att_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    result = attachment_service.get_attachment_file(db, att_id, user.id)
    if not result:
        raise HTTPException(status_code=404)
    filepath, original_filename, mime_type = result
    from fastapi.responses import FileResponse
    return FileResponse(filepath, filename=original_filename, media_type=mime_type)

@router.post("/attachments/{att_id}/delete")
def attachment_delete(request: Request, att_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], redirect_url: str = Form("/dashboard")):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    attachment_service.delete_attachment(db, att_id, user.id)
    return RedirectResponse(url=redirect_url, status_code=303)


# --- Admin (Kullanici Yonetimi) ---

@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if not hasattr(user, 'role') or user.role != "admin":
        raise HTTPException(status_code=403, detail="Yetkisiz erisim")
    users = db.query(User).all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "user": user, "active_page": "admin", "users": users,
    })

@router.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
def admin_user_edit(request: Request, user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if not hasattr(user, 'role') or user.role != "admin":
        raise HTTPException(status_code=403, detail="Yetkisiz erisim")
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("admin/user_edit.html", {
        "request": request, "user": user, "active_page": "admin", "edit_user": target_user,
    })

@router.post("/admin/users/{user_id}/edit")
def admin_user_update(request: Request, user_id: uuid.UUID, db: Annotated[Session, Depends(get_db)],
    role: str = Form(...), is_active: str = Form("off"),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if not hasattr(user, 'role') or user.role != "admin":
        raise HTTPException(status_code=403, detail="Yetkisiz erisim")
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)
    target_user.role = role
    target_user.is_active = is_active in ("on", "1")
    db.commit()
    activity_service.log_activity(db, user.id, "update", "user", user_id, f"Kullanici guncellendi: {target_user.email} -> {role}")
    return RedirectResponse(url="/admin/users", status_code=303)


# --- 2FA ---

@router.get("/settings/2fa", response_class=HTMLResponse)
def two_factor_setup_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if user.totp_secret:
        return templates.TemplateResponse("auth/two_factor_setup.html", {
            "request": request, "user": user, "active_page": "settings", "enabled": True,
        })
    secret = totp_service.generate_totp_secret()
    uri = totp_service.get_totp_uri(secret, user.email)
    import base64
    qr_bytes = totp_service.generate_qr_code(uri)
    qr_b64 = base64.b64encode(qr_bytes).decode()
    return templates.TemplateResponse("auth/two_factor_setup.html", {
        "request": request, "user": user, "active_page": "settings",
        "enabled": False, "secret": secret, "qr_b64": qr_b64,
    })

@router.post("/settings/2fa/enable")
def two_factor_enable(request: Request, db: Annotated[Session, Depends(get_db)],
    secret: str = Form(...), code: str = Form(...),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if totp_service.verify_totp(secret, code):
        user.totp_secret = secret
        db.commit()
        return RedirectResponse(url="/settings", status_code=303)
    return templates.TemplateResponse("auth/two_factor_setup.html", {
        "request": request, "user": user, "active_page": "settings",
        "enabled": False, "secret": secret, "error": "Gecersiz dogrulama kodu",
    })

@router.post("/settings/2fa/disable")
def two_factor_disable(request: Request, db: Annotated[Session, Depends(get_db)], code: str = Form(...)):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    if user.totp_secret and totp_service.verify_totp(user.totp_secret, code):
        user.totp_secret = None
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)


# ---------------------------------------------------------------------------
# Bildirim Merkezi Sayfasi
# ---------------------------------------------------------------------------
@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    filter: str = Query("all"),
):
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    size = 20
    unread_only = filter == "unread"
    offset = (page - 1) * size

    notifications = notification_service.get_notifications(
        db, user.id, unread_only=unread_only, limit=size, offset=offset
    )
    unread_count = notification_service.get_unread_count(db, user.id)

    # Toplam bildirim sayisi (filtre'ye gore)
    if unread_only:
        total = unread_count
    else:
        total = len(notification_service.get_notifications(db, user.id, limit=10000))

    total_pages = max(1, (total + size - 1) // size)

    return templates.TemplateResponse("notifications/list.html", {
        "request": request,
        "user": user,
        "active_page": "notifications",
        "notifications": notifications,
        "unread_count": unread_count,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "current_filter": filter,
    })


# ---------------------------------------------------------------------------
# Satis Pipeline (Kanban Board) Sayfalari
# ---------------------------------------------------------------------------
@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_kanban(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Kanban board gorunumu."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    stages = deal_service.ensure_default_stages(db, user.id)
    # Her asamadaki deal'lari yukle
    for stage in stages:
        stage.deals = deal_service.get_deals(db, user.id, stage_id=stage.id)

    stats = deal_service.get_pipeline_stats(db, user.id)
    customers, _ = customer_service.get_customers(db, user.id)

    return templates.TemplateResponse("pipeline/kanban.html", {
        "request": request, "user": user, "active_page": "pipeline",
        "stages": stages, "stats": stats, "customers": customers,
    })


@router.post("/pipeline/new")
def pipeline_deal_create(
    request: Request, db: Annotated[Session, Depends(get_db)],
    title: str = Form(...), stage_id: uuid.UUID = Form(...),
    customer_id: str = Form(""), value: str = Form("0"),
    probability: int = Form(50), expected_close_date: str = Form(""),
    priority: str = Form("medium"), notes: str = Form(""),
):
    """Yeni satis firsati olustur."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from decimal import Decimal
    from datetime import date

    deal = deal_service.create_deal(
        db, user.id,
        title=title,
        stage_id=stage_id,
        customer_id=uuid.UUID(customer_id) if customer_id else None,
        value=Decimal(value) if value else Decimal("0"),
        probability=probability,
        expected_close_date=date.fromisoformat(expected_close_date) if expected_close_date else None,
        notes=notes or None,
        priority=priority,
    )
    activity_service.log_activity(db, user.id, "deal", "create", str(deal.id), f"Satis firsati olusturuldu: {title}")
    return RedirectResponse(url="/pipeline", status_code=303)


@router.get("/pipeline/{deal_id}/edit", response_class=HTMLResponse)
def pipeline_deal_edit_form(deal_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Firsat duzenleme formu."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    deal = deal_service.get_deal(db, deal_id, user.id)
    if not deal:
        return RedirectResponse(url="/pipeline", status_code=303)
    stages = deal_service.get_stages(db, user.id)
    customers, _ = customer_service.get_customers(db, user.id)

    return templates.TemplateResponse("pipeline/edit.html", {
        "request": request, "user": user, "active_page": "pipeline",
        "deal": deal, "stages": stages, "customers": customers,
    })


@router.post("/pipeline/{deal_id}/edit")
def pipeline_deal_edit_submit(
    deal_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)],
    title: str = Form(...), stage_id: uuid.UUID = Form(...),
    customer_id: str = Form(""), value: str = Form("0"),
    probability: int = Form(50), expected_close_date: str = Form(""),
    priority: str = Form("medium"), notes: str = Form(""),
):
    """Firsat guncelle."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    from decimal import Decimal
    from datetime import date

    deal_service.update_deal(
        db, deal_id, user.id,
        title=title,
        stage_id=stage_id,
        customer_id=uuid.UUID(customer_id) if customer_id else None,
        value=Decimal(value) if value else Decimal("0"),
        probability=probability,
        expected_close_date=date.fromisoformat(expected_close_date) if expected_close_date else None,
        notes=notes or None,
        priority=priority,
    )
    return RedirectResponse(url="/pipeline", status_code=303)


@router.get("/pipeline/{deal_id}/delete")
def pipeline_deal_delete(deal_id: uuid.UUID, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Firsat sil."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    deal_service.delete_deal(db, deal_id, user.id)
    return RedirectResponse(url="/pipeline", status_code=303)


# ---------------------------------------------------------------------------
# AI Asistan Sayfasi
# ---------------------------------------------------------------------------
@router.get("/ai-assistant", response_class=HTMLResponse)
def ai_assistant_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """AI Asistan sayfasi."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    insights = ai_assistant.get_dashboard_insights(db, user.id)

    return templates.TemplateResponse("ai/assistant.html", {
        "request": request, "user": user, "active_page": "ai",
        "insights": insights,
    })


# ---------------------------------------------------------------------------
# WhatsApp Mesajlari
# ---------------------------------------------------------------------------
@router.get("/whatsapp", response_class=HTMLResponse)
def whatsapp_messages_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """WhatsApp mesaj gecmisi sayfasi."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    messages = whatsapp_service.get_message_history(db, user.id)
    customers, _ = customer_service.get_customers(db, user.id, size=9999)
    invoices, _ = invoice_service.get_invoices(db, user.id, size=9999)

    return templates.TemplateResponse("whatsapp/messages.html", {
        "request": request, "user": user, "active_page": "whatsapp",
        "messages": messages, "customers": customers, "invoices": invoices,
    })


@router.post("/whatsapp/send")
def whatsapp_send(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    customer_id: uuid.UUID = Form(...),
    message_type: str = Form("custom"),
    invoice_id: uuid.UUID | None = Form(None),
    message_text: str | None = Form(None),
):
    """WhatsApp mesaji gonder."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    customer = customer_service.get_customer(db, customer_id, user.id)
    if not customer:
        return RedirectResponse(url="/whatsapp", status_code=303)

    if message_type == "invoice_send" and invoice_id:
        invoice = invoice_service.get_invoice(db, invoice_id, user.id)
        if invoice:
            whatsapp_service.send_invoice(db, user.id, invoice, customer)
    elif message_type == "payment_reminder" and invoice_id:
        invoice = invoice_service.get_invoice(db, invoice_id, user.id)
        if invoice:
            whatsapp_service.send_payment_reminder(db, user.id, invoice, customer)
    elif message_text:
        whatsapp_service.send_custom_message(db, user.id, customer, message_text)

    return RedirectResponse(url="/whatsapp", status_code=303)


# ---------------------------------------------------------------------------
# Ozel Alanlar (Custom Fields)
# ---------------------------------------------------------------------------
@router.get("/custom-fields", response_class=HTMLResponse)
def custom_fields_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Ozel alan yonetim sayfasi."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    fields = custom_field_service.get_definitions(db, user.id)
    entity_types = [
        {"key": "all", "label": "Tumunu Goster"},
        {"key": "customer", "label": "Musteri"},
        {"key": "invoice", "label": "Fatura"},
        {"key": "product", "label": "Urun"},
        {"key": "deal", "label": "Firsat"},
    ]

    return templates.TemplateResponse("custom_fields/manage.html", {
        "request": request, "user": user, "active_page": "custom_fields",
        "fields": fields, "entity_types": entity_types,
    })


@router.post("/custom-fields/new")
def custom_fields_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    entity_type: str = Form(...),
    field_name: str = Form(...),
    field_type: str = Form(...),
    options_text: str | None = Form(None),
    is_required: str | None = Form(None),
):
    """Yeni ozel alan olustur."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    options = None
    if field_type == "select" and options_text:
        options = [o.strip() for o in options_text.strip().split("\n") if o.strip()]

    custom_field_service.create_definition(
        db, user.id,
        entity_type=entity_type,
        field_name=field_name,
        field_type=field_type,
        options=options,
        is_required=bool(is_required),
    )

    return RedirectResponse(url="/custom-fields", status_code=303)


@router.get("/custom-fields/{field_id}/delete")
def custom_fields_delete(
    request: Request, field_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Ozel alani sil."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    custom_field_service.delete_definition(db, user.id, field_id)
    return RedirectResponse(url="/custom-fields", status_code=303)


# ---------------------------------------------------------------------------
# Onboarding (Ilk Kullanim Wizard)
# ---------------------------------------------------------------------------
@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    """Onboarding wizard sayfasi."""
    user = require_login(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse("onboarding.html", {
        "request": request, "user": user, "active_page": "onboarding",
    })


@router.post("/onboarding/add-customer")
async def onboarding_add_customer(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Onboarding sirasinda ilk musteriyi ekle."""
    user = require_login(request, db)
    if not user:
        return JSONResponse({"error": "auth"}, status_code=401)

    form_data = await request.form()
    company_name = form_data.get("company_name", "").strip()
    if not company_name:
        return JSONResponse({"error": "name required"}, status_code=400)

    data = CustomerCreate(
        company_name=company_name,
        email=form_data.get("email", "").strip() or None,
        phone=form_data.get("phone", "").strip() or None,
    )
    customer_service.create_customer(db, user.id, data)
    return JSONResponse({"ok": True})
