from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from kolayis.database import get_db
from kolayis.services.auth import verify_token
from kolayis.models.user import User

# OAuth2PasswordBearer: Swagger UI'da "Authorize" butonu gosterir
# tokenUrl: login endpoint'inin adresi
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    JWT token'dan mevcut kullaniciyi dondur.

    Bu fonksiyon FastAPI'nin Depends sistemi ile calisir:
    1. Istek gelir -> Authorization header'indan token alinir
    2. Token dogrulanir -> icinden user_id cikarilir
    3. Veritabanindan kullanici bulunur ve dondurulur

    Kullanim:
        @router.get("/")
        def endpoint(user: User = Depends(get_current_user)):
            ...
    """
    user_id = verify_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanici bulunamadi veya aktif degil",
        )
    return user
