"""
Musteri Portali servis katmani.
Portal erisim olusturma, dogrulama, deaktif etme ve PIN sifirlama islemleri.
"""

import uuid
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from kolayis.models.portal import PortalAccess

# PIN hashleme icin ayni guvenli yontemi kullaniyoruz
_password_hash = PasswordHash.recommended()


def generate_access_token() -> str:
    """
    Benzersiz erisim kodu uret.
    secrets.token_urlsafe(32) ile 43 karakterlik URL-safe token olusturur.
    Musteriye bu kod verilir, portal girisinde kullanir.
    """
    return secrets.token_urlsafe(32)


def _hash_pin(pin: str) -> str:
    """PIN'i guvenli sekilde hashle."""
    return _password_hash.hash(pin)


def _verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Girilen PIN'i hashlenmis PIN ile karsilastir."""
    return _password_hash.verify(plain_pin, hashed_pin)


def create_portal_access(
    db: Session,
    owner_id: uuid.UUID,
    customer_id: uuid.UUID,
    pin: str,
) -> PortalAccess:
    """
    Musteri icin portal erisimi olustur.
    - PIN hashlenir
    - Benzersiz access_token uretilir
    - Ayni musteriye tekrar erisim olusturulursa eski erisim guncellenir

    owner_id: Bu musterinin sahibi olan kullanici (yetki kontrolu icin)
    customer_id: Portal erisimi verilecek musteri
    pin: 4-6 haneli PIN (duz metin olarak gelir, burada hashlenir)
    """
    # Mevcut erisim var mi kontrol et
    existing = (
        db.query(PortalAccess)
        .filter(PortalAccess.customer_id == customer_id)
        .first()
    )

    if existing:
        # Varsa guncelle: yeni token, yeni PIN
        existing.access_token = generate_access_token()
        existing.pin_hash = _hash_pin(pin)
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    # Yeni erisim olustur
    portal_access = PortalAccess(
        customer_id=customer_id,
        access_token=generate_access_token(),
        pin_hash=_hash_pin(pin),
        is_active=True,
    )
    db.add(portal_access)
    db.commit()
    db.refresh(portal_access)
    return portal_access


def verify_portal_login(
    db: Session,
    access_token: str,
    pin: str,
) -> PortalAccess | None:
    """
    Portal giris dogrulamasi.
    Erisim kodu ve PIN'i kontrol eder.
    Basarili: PortalAccess dondurur, last_login gunceller.
    Basarisiz: None dondurur.
    """
    portal_access = (
        db.query(PortalAccess)
        .filter(
            PortalAccess.access_token == access_token,
            PortalAccess.is_active == True,
        )
        .first()
    )

    if not portal_access:
        return None

    # PIN dogrula
    if not _verify_pin(pin, portal_access.pin_hash):
        return None

    # Son giris zamanini guncelle
    portal_access.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(portal_access)
    return portal_access


def get_portal_access_by_customer(
    db: Session,
    customer_id: uuid.UUID,
) -> PortalAccess | None:
    """Musterinin portal erisimini getir (varsa)."""
    return (
        db.query(PortalAccess)
        .filter(PortalAccess.customer_id == customer_id)
        .first()
    )


def deactivate_portal_access(
    db: Session,
    portal_id: uuid.UUID,
) -> bool:
    """
    Portal erisimini deaktif et.
    Musteri artik portale giris yapamaz.
    Dondurur: True (basarili), False (bulunamadi)
    """
    portal_access = (
        db.query(PortalAccess)
        .filter(PortalAccess.id == portal_id)
        .first()
    )
    if not portal_access:
        return False

    portal_access.is_active = False
    db.commit()
    return True


def reset_pin(
    db: Session,
    portal_id: uuid.UUID,
    new_pin: str,
) -> PortalAccess:
    """
    Portal PIN'ini sifirla.
    Yeni PIN hashlenerek kaydedilir.
    """
    portal_access = (
        db.query(PortalAccess)
        .filter(PortalAccess.id == portal_id)
        .first()
    )
    if not portal_access:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portal erisimi bulunamadi",
        )

    portal_access.pin_hash = _hash_pin(new_pin)
    db.commit()
    db.refresh(portal_access)
    return portal_access
