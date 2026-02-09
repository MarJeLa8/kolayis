"""
Musteri Portali router'i.
Musterilerin kendi faturalarini gorup odeme durumunu takip edebilecegi
ayri bir web arayuzu saglar.

Ana CRM'den tamamen bagimsiz bir giris sistemi kullanir:
- Erisim kodu (access_token) + PIN ile giris
- Cookie'de portal_token saklenir
- Kendi base template'ini (portal/base.html) kullanir
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.models.portal import PortalAccess
from kolayis.models.invoice import Invoice
from kolayis.services import portal as portal_service

router = APIRouter(prefix="/portal", tags=["Musteri Portali"])
templates = Jinja2Templates(directory="kolayis/templates")


# --- Yardimci fonksiyonlar ---

def get_portal_user_from_cookie(request: Request, db: Session) -> PortalAccess | None:
    """
    Cookie'deki portal_token'dan portal erisimini dondur.
    Token yoksa veya gecersizse None dondurur.
    """
    token = request.cookies.get("portal_token")
    if not token:
        return None
    try:
        portal_access = (
            db.query(PortalAccess)
            .filter(
                PortalAccess.access_token == token,
                PortalAccess.is_active == True,
            )
            .first()
        )
        return portal_access
    except Exception:
        return None


def require_portal_login(request: Request, db: Session) -> PortalAccess | None:
    """Portal giris kontrolu. Giris yapilmamissa None dondurur."""
    return get_portal_user_from_cookie(request, db)


# --- Portal giris sayfalari ---

@router.get("/login", response_class=HTMLResponse)
def portal_login_page(request: Request):
    """Portal giris sayfasi"""
    return templates.TemplateResponse("portal/login.html", {
        "request": request,
    })


@router.post("/login", response_class=HTMLResponse)
def portal_login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    access_token: str = Form(...),
    pin: str = Form(...),
):
    """
    Portal giris formu gonderildiginde.
    Erisim kodu + PIN dogrulanir, basariliysa cookie set edilir.
    """
    # Erisim kodu ve PIN dogrula
    portal_access = portal_service.verify_portal_login(db, access_token, pin)

    if not portal_access:
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "error": "Erisim kodu veya PIN hatali",
        })

    # Cookie'ye erisim kodunu kaydet
    response = RedirectResponse(url="/portal/dashboard", status_code=303)
    response.set_cookie(
        key="portal_token",
        value=portal_access.access_token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def portal_logout():
    """Portal cikis - cookie'yi sil"""
    response = RedirectResponse(url="/portal/login", status_code=303)
    response.delete_cookie(key="portal_token")
    return response


# --- Portal dashboard ---

@router.get("/dashboard", response_class=HTMLResponse)
def portal_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Musteri portal dashboard'u.
    Toplam borc, odenmis tutar, bekleyen faturalar ozeti.
    """
    portal_access = require_portal_login(request, db)
    if not portal_access:
        return RedirectResponse(url="/portal/login", status_code=303)

    customer = portal_access.customer

    # Bu musterinin tum faturalarini getir (iptal edilmemis olanlar)
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer.id,
            Invoice.status != "cancelled",
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )

    # Istatistikler
    total_amount = sum(inv.total for inv in invoices)
    paid_amount = sum(inv.paid_amount for inv in invoices)
    remaining_amount = sum(inv.remaining_amount for inv in invoices)

    # Fatura durum sayilari
    paid_count = sum(1 for inv in invoices if inv.status == "paid")
    pending_count = sum(1 for inv in invoices if inv.status in ("draft", "sent"))

    # Vadesi gecen faturalar
    from datetime import date as date_cls
    today = date_cls.today()
    overdue_invoices = [
        inv for inv in invoices
        if inv.due_date and inv.status in ("sent", "draft") and inv.due_date < today
    ]
    overdue_amount = sum(inv.remaining_amount for inv in overdue_invoices)

    return templates.TemplateResponse("portal/dashboard.html", {
        "request": request,
        "portal_access": portal_access,
        "customer": customer,
        "active_page": "dashboard",
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
        "paid_count": paid_count,
        "pending_count": pending_count,
        "overdue_count": len(overdue_invoices),
        "overdue_amount": overdue_amount,
        "recent_invoices": invoices[:5],
        "today": today,
    })


# --- Portal fatura listesi ---

@router.get("/invoices", response_class=HTMLResponse)
def portal_invoices(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Musteri faturalari listesi."""
    portal_access = require_portal_login(request, db)
    if not portal_access:
        return RedirectResponse(url="/portal/login", status_code=303)

    customer = portal_access.customer

    # Bu musterinin tum faturalarini getir
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )

    from datetime import date as date_cls
    today = date_cls.today()

    return templates.TemplateResponse("portal/invoices.html", {
        "request": request,
        "portal_access": portal_access,
        "customer": customer,
        "active_page": "invoices",
        "invoices": invoices,
        "today": today,
    })


# --- Portal fatura detay ---

@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def portal_invoice_detail(
    invoice_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Fatura detay sayfasi (portal gorunumu)."""
    portal_access = require_portal_login(request, db)
    if not portal_access:
        return RedirectResponse(url="/portal/login", status_code=303)

    customer = portal_access.customer

    # Fatura bu musteriye ait mi kontrol et
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.customer_id == customer.id,
        )
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadi")

    from datetime import date as date_cls
    today = date_cls.today()

    return templates.TemplateResponse("portal/invoice_detail.html", {
        "request": request,
        "portal_access": portal_access,
        "customer": customer,
        "active_page": "invoices",
        "invoice": invoice,
        "today": today,
    })
