import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import HTTPException, status

from kolayis.config import settings

# Sifre hashleme icin Argon2 kullaniyoruz (en guvenli yontem)
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Duz metin sifreyi hashle. Veritabanina bu hash kaydedilir."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kullanicinin girdigi sifreyi, veritabanindaki hash ile karsilastir."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID) -> str:
    """
    JWT token olustur.
    Token icinde kullanici ID'si ve son kullanma tarihi var.
    Bu token her istekte Authorization header'inda gonderilir.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> uuid.UUID:
    """
    JWT token'i dogrula ve icindeki kullanici ID'sini dondur.
    Token gecersizse veya suresi dolmussa hata firlatir.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Gecersiz token",
            )
        return uuid.UUID(user_id)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz token",
        )
